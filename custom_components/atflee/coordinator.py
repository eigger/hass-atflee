"""Data coordinator for the Atflee integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from time import monotonic

from blesession import SessionReports, fallback_report, stages
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .atflee_ble.bodycomp import IMPEDANCE_CHANNELS, calculate_body_composition
from .atflee_ble.connection import AtfleeBleClient
from .atflee_ble.profile import age_from_birth_date
from .const import (
    CONF_NOTIFY_TIMEOUT_SECONDS,
    DOMAIN,
    GATT_PROFILES,
    SUBENTRY_TYPE_USER,
)
from .atflee_ble.models import AtfleeMeasurement, AtfleeState, next_state
from .session_report import ARM, MEASURE, SessionTrace, build_session_report
from .user_profile import primary_user_id, profile_from_data

_LOGGER = logging.getLogger(__name__)

# Reliable fallback poll. HA's bluetooth manager de-duplicates advertisements
# whose payload is unchanged, and this scale advertises a *static* payload
# (fixed local name, no changing manufacturer/service data). So after the first
# sighting is cached, _async_on_advertisement stops firing and a session can
# never be started again from adverts alone. The watchdog polls device presence
# instead, which is unaffected by de-duplication.
WATCHDOG_INTERVAL = timedelta(seconds=5)


# PEP 695 alias: evaluated lazily, so the forward reference is fine.
type AtfleeConfigEntry = ConfigEntry[AtfleeDataUpdateCoordinator]


class AtfleeDataUpdateCoordinator(DataUpdateCoordinator[AtfleeState]):
    """Coordinate BLE updates for one Atflee scale.

    Flow:
    1) Wait for advertisement callback from HA bluetooth.
    2) Open one GATT session, subscribe notify.
    3) Keep session while notifications keep arriving.
    4) Disconnect when idle timeout passes without packet.
    """

    def __init__(self, hass: HomeAssistant, entry: AtfleeConfigEntry) -> None:
        self.entry = entry
        self._warned_no_profile: set[str | None] = set()
        self.address: str = entry.data[CONF_ADDRESS]
        self.client = AtfleeBleClient(hass, self.address)
        self._adv_unsub = None
        self._watchdog_unsub = None
        # True once a session has been started for the current awake period.
        # Reset when the device goes absent (scale slept / out of range) so the
        # next reappearance is treated as a fresh wake and gets exactly one
        # session -- instead of reconnecting in a loop while it keeps
        # advertising. See _async_watchdog / _maybe_start_session.
        self._handled_current_presence: bool = False
        self._session_task: asyncio.Task | None = None
        self._session_lock = asyncio.Lock()
        # Failure count / last failure time for the diagnostic sensors. Resets
        # on entry reload; only sessions that ended in an error are counted.
        self.session_reports = SessionReports()
        # Retries inside one wake (watchdog re-fires every few seconds while the
        # scale stays present) count as one failure, not one per attempt.
        self._failure_recorded_this_wake: bool = False
        # True while a session runs, so the Connection Duration sensor does not
        # show the previous session's breakdown against this one's time.
        self.session_report_pending: bool = False
        self._connected_started_monotonic: float | None = None
        self._last_session_end_monotonic: float = 0.0
        self._reconnect_cooldown_seconds: float = 5.0
        # Diagnostics: count every advertisement callback fire and accepted
        # session trigger so it is unambiguous from the logs whether the BLE
        # stack stopped delivering advertisements or whether we are receiving
        # them but skipping the trigger.
        self._adv_callback_count: int = 0
        self._session_trigger_count: int = 0
        self._last_adv_monotonic: float | None = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{self.address}",
            update_interval=None,
        )

    async def async_start(self) -> None:
        """Start advertisement-driven update flow."""
        if self._adv_unsub is not None:
            _LOGGER.debug(
                "Atflee adv callback already registered for %s; skip re-register",
                self.address,
            )
            return
        self._adv_unsub = bluetooth.async_register_callback(
            self.hass,
            self._async_on_advertisement,
            {"address": self.address},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
        _LOGGER.debug(
            "Atflee adv callback registered: address=%s mode=ACTIVE", self.address
        )
        # Fallback trigger that does not depend on advertisement callbacks (see
        # WATCHDOG_INTERVAL): polls presence and starts one session per wake.
        self._watchdog_unsub = async_track_time_interval(
            self.hass, self._async_watchdog, WATCHDOG_INTERVAL
        )

    async def async_stop(self) -> None:
        """Stop callbacks and running session."""
        if self._watchdog_unsub is not None:
            self._watchdog_unsub()
            self._watchdog_unsub = None
        if self._adv_unsub is not None:
            self._adv_unsub()
            self._adv_unsub = None
            _LOGGER.debug("Atflee adv callback unregistered: address=%s", self.address)
        if self._session_task is not None and not self._session_task.done():
            self._session_task.cancel()
            try:
                await self._session_task
            except asyncio.CancelledError:
                pass
        await self.client.disconnect()

    @callback
    def _async_on_advertisement(self, service_info, change) -> None:
        """Start one session when advertisement is received."""
        self._adv_callback_count += 1
        now = monotonic()
        gap = (
            f"{now - self._last_adv_monotonic:.2f}s"
            if self._last_adv_monotonic is not None
            else "first"
        )
        self._last_adv_monotonic = now

        # Surface every adv fire with enough context to tell apart "BLE stack
        # stopped delivering ads" from "ad delivered but trigger skipped".
        rssi = getattr(service_info, "rssi", None)
        name = getattr(service_info, "name", None) or getattr(
            getattr(service_info, "advertisement", None), "local_name", None
        )
        connectable = getattr(service_info, "connectable", None)
        service_uuids = list(getattr(service_info, "service_uuids", []) or [])
        _LOGGER.debug(
            "Atflee adv callback fired: address=%s count=%d gap=%s "
            "change=%s rssi=%s name=%s connectable=%s services=%s",
            self.address,
            self._adv_callback_count,
            gap,
            change,
            rssi,
            name,
            connectable,
            service_uuids,
        )

        # An advertisement is a strong wake signal; try to start a session.
        self._maybe_start_session("advertisement")

    @callback
    def _async_watchdog(self, _now=None) -> None:
        """Poll presence and start a session when adverts are de-duplicated.

        The advertisement callback is only a fast path. Because HA de-duplicates
        this scale's static advertisement, it stops firing after the first
        sighting -- so reconnection cannot rely on it. Here we poll device
        presence: when the scale is absent (asleep / out of range) we re-arm,
        and when it is present and not yet handled for this wake we start one
        session.
        """
        if self._adv_unsub is None:
            return
        present = (
            bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            is not None
        )
        if not present:
            # Scale slept / out of range: arm so its next appearance is a fresh
            # wake that gets its own session.
            if self._handled_current_presence:
                _LOGGER.debug(
                    "Atflee watchdog: %s now absent; re-arming for next wake",
                    self.address,
                )
            self._handled_current_presence = False
            self._failure_recorded_this_wake = False
            return
        if self._handled_current_presence:
            return
        self._maybe_start_session("watchdog")

    def _maybe_start_session(self, reason: str) -> None:
        """Start one measurement session if not in cooldown / already running.

        Marks the current presence handled so we run exactly one session per
        wake rather than looping while the scale keeps advertising.
        """
        now = monotonic()

        # Skip: still within the post-session cooldown window.
        remaining_cooldown = self._reconnect_cooldown_seconds - (
            now - self._last_session_end_monotonic
        )
        if remaining_cooldown > 0:
            _LOGGER.debug(
                "Atflee session trigger skipped (cooldown): address=%s reason=%s "
                "remaining=%.2fs",
                self.address,
                reason,
                remaining_cooldown,
            )
            return

        # Skip: a previous session task has not finished yet.
        if self._session_task is not None and not self._session_task.done():
            _LOGGER.debug(
                "Atflee session trigger skipped (session busy): address=%s reason=%s",
                self.address,
                reason,
            )
            return

        self._session_trigger_count += 1
        self._handled_current_presence = True
        _LOGGER.debug(
            "Atflee session trigger accepted: address=%s reason=%s session=#%d adv_count=%d",
            self.address,
            reason,
            self._session_trigger_count,
            self._adv_callback_count,
        )
        self._session_task = self.hass.async_create_task(self._run_measurement_session())

    def user_subentries(self) -> dict[str, ConfigSubentry]:
        """Return the configured user subentries by subentry id."""
        return {
            sid: sub
            for sid, sub in self.entry.subentries.items()
            if sub.subentry_type == SUBENTRY_TYPE_USER
        }

    def _resolve_user(self, measurement: AtfleeMeasurement | None = None) -> str | None:
        """Return the subentry id a measurement belongs to, or None without users.

        ``measurement`` is None when asked before any weight is known (the profile
        pushed to the scale on connect). Currently every measurement is attributed
        to the primary user (lowest slot); this is the single place where a user
        selection or weight-based identification plugs in. With no users configured
        nothing is attributed: the packet only updates the scale-level state.
        """
        users = self.user_subentries()
        return primary_user_id({sid: sub.data for sid, sub in users.items()})

    def _profile(self, user_id: str | None) -> tuple[int, int, str] | None:
        """Return (height_cm, age, sex) of a user, or None if unavailable."""
        sub = self.entry.subentries.get(user_id) if user_id else None
        profile = profile_from_data(sub.data) if sub else None
        if profile is None:
            if user_id not in self._warned_no_profile:
                self._warned_no_profile.add(user_id)
                _LOGGER.warning(
                    "Atflee: no usable user profile is configured; body metrics are "
                    "skipped. Add a user from the integration page"
                )
            return None
        age = max(1, age_from_birth_date(profile.birth_date, dt_util.now().date()))
        return profile.height_cm, age, profile.sex

    def _apply_body_composition(
        self, measurement: AtfleeMeasurement, user_id: str | None
    ) -> None:
        """Fill the composition fields from a full impedance set, if present."""
        if (
            measurement.weight_kg is None
            or measurement.impedances_ohm is None
            or len(measurement.impedances_ohm) < IMPEDANCE_CHANNELS
        ):
            return
        profile = self._profile(user_id)
        if profile is None:
            return
        height_cm, age, sex = profile
        result = calculate_body_composition(
            measurement.weight_kg,
            height_cm,
            age,
            sex.lower() in ("male", "m", "1"),
            measurement.impedances_ohm,
        )
        if result is None:
            _LOGGER.debug(
                "Atflee body composition skipped: height=%s age=%s weight=%s",
                height_cm,
                age,
                measurement.weight_kg,
            )
            return
        measurement.bmi = round(result.bmi, 1)
        measurement.body_fat_pct = result.body_fat_pct
        measurement.subcutaneous_fat_pct = result.subcutaneous_fat_pct
        measurement.visceral_fat = result.visceral_fat
        measurement.muscle_pct = result.muscle_pct
        measurement.muscle_mass = result.muscle_mass_kg
        measurement.bmr = result.bmr_kcal
        measurement.bone_mass = round(result.bone_mass_kg, 2)
        measurement.moisture_pct = result.water_pct
        measurement.protein_pct = result.protein_pct
        measurement.skeletal_muscle_pct = result.skeletal_muscle_pct
        measurement.physical_age = result.physical_age
        measurement.body_score = float(result.body_score)
        measurement.measure_state = "body_composition"
        measurement.is_body_composition_complete = True

    def _idle_timeout_seconds(self) -> float:
        return float(
            self.entry.options.get(
                CONF_NOTIFY_TIMEOUT_SECONDS,
                self.entry.data[CONF_NOTIFY_TIMEOUT_SECONDS],
            )
        )

    def _build_state(
        self,
        *,
        measurement: AtfleeMeasurement | None = None,
        user_id: str | None = None,
        connected: bool,
        measuring: bool,
    ) -> AtfleeState:
        prev = self.data if isinstance(self.data, AtfleeState) else None
        now = datetime.utcnow()

        if connected:
            if self._connected_started_monotonic is None:
                self._connected_started_monotonic = monotonic()
                connection_started_at = now
                duration_seconds = 0
            else:
                duration_seconds = int(monotonic() - self._connected_started_monotonic)
                connection_started_at = (
                    prev.connection_started_at if prev and prev.connection_started_at else now
                )
        else:
            self._connected_started_monotonic = None
            duration_seconds = prev.connection_duration_seconds if prev else 0
            connection_started_at = prev.connection_started_at if prev else None

        return next_state(
            prev,
            measurement=measurement,
            user_id=user_id,
            connected=connected,
            measuring=measuring,
            connection_started_at=connection_started_at,
            connection_duration_seconds=duration_seconds,
            updated_at=now,
        )

    def _merge_with_previous_measurement(
        self, measurement: AtfleeMeasurement, user_id: str | None
    ) -> AtfleeMeasurement:
        """Preserve this user's last known values when control packets omit them."""
        prev = self.data if isinstance(self.data, AtfleeState) else None
        prev_measurement = prev.measurements.get(user_id) if prev and user_id else None
        measurement.merge_with_previous(prev_measurement)
        return measurement

    async def _run_measurement_session(self) -> None:
        """Run one connect/notify session triggered by advertisement."""
        async with self._session_lock:
            ble_device = bluetooth.async_ble_device_from_address(self.hass, self.address)
            if ble_device is None:
                _LOGGER.debug("Adv trigger but BLE device unavailable: %s", self.address)
                # Never actually connected; let the watchdog retry this wake.
                self._handled_current_presence = False
                return
            _LOGGER.debug(
                "Atflee session start: address=%s name=%s rssi=%s",
                self.address,
                ble_device.name,
                getattr(ble_device, "rssi", None),
            )

            idle_timeout = self._idle_timeout_seconds()
            connected = False
            outcome: BaseException | None = None
            cancelled = False
            trace = SessionTrace()
            packets = 0
            arm_started: float | None = None
            measure_started: float | None = None
            self.session_report_pending = True
            try:
                with trace.timed(stages.CONNECT):
                    await self.client.connect_with_profiles(
                        ble_device=ble_device,
                        profiles=GATT_PROFILES,
                    )
                connected = True
                arm_started = monotonic()
                self._failure_recorded_this_wake = False
                _LOGGER.debug(
                    "Atflee session connected: address=%s idle_timeout=%.1fs",
                    self.address,
                    idle_timeout,
                )
                
                # Push the user profile (B1) on connect, with the impedance
                # function enabled, so the scale measures impedance after the
                # weight settles. Its A1/A3/A5/A7 messages are acked below.
                from .atflee_ble.packet import ACKED_COMMANDS
                from .atflee_ble.protocol import (
                    build_reply_frames,
                    build_user_info_frames,
                )
                from .const import (
                    CONF_ENABLE_BODY_COMP,
                    DEFAULT_ENABLE_BODY_COMP,
                )

                send_enabled = bool(
                    self.entry.options.get(
                        CONF_ENABLE_BODY_COMP,
                        self.entry.data.get(
                            CONF_ENABLE_BODY_COMP, DEFAULT_ENABLE_BODY_COMP
                        ),
                    )
                )

                profile = self._profile(self._resolve_user()) if send_enabled else None
                if profile is not None:
                    now_local = dt_util.now()
                    height_cm, age, sex = profile
                    # Standard (non-DST) offset, like the scale's own clock setup.
                    utc_offset = (now_local.utcoffset() or timedelta(0)) - (
                        now_local.dst() or timedelta(0)
                    )
                    user_info_frames = build_user_info_frames(
                        sex=sex,
                        age=age,
                        height_cm=height_cm,
                        pkg_index=self.client.next_pkg_index(),
                        timestamp=int(now_local.timestamp()),
                        utc_offset_seconds=int(utc_offset.total_seconds()),
                    )
                    await self.client.send_frames(user_info_frames)
                else:
                    _LOGGER.debug(
                        "Atflee body composition measurement skipped (%s)",
                        "disabled" if not send_enabled else "no user profile",
                    )

                self.async_set_updated_data(self._build_state(connected=True, measuring=True))

                trace.record(ARM, monotonic() - arm_started)
                arm_started = None
                measure_started = monotonic()
                last_event = monotonic()
                while True:
                    remaining = idle_timeout - (monotonic() - last_event)
                    if remaining <= 0:
                        break
                    measurement = await self.client.wait_for_measurement(timeout_seconds=remaining)
                    last_event = monotonic()
                    packets += 1
                    _LOGGER.debug(
                        "Atflee measurement packet parsed: weight=%s bmi=%s body_fat=%s imp=%s state=%s stable=%s complete=%s raw=%s",
                        measurement.weight_kg,
                        measurement.bmi,
                        measurement.body_fat_pct,
                        measurement.impedance_ohm,
                        measurement.measure_state,
                        measurement.is_stable,
                        measurement.is_body_composition_complete,
                        measurement.raw_hex,
                    )

                    # The scale retransmits device info, stable weight and
                    # upload messages until they are answered with a B0 ack
                    # that echoes the message's package index.
                    if (
                        measurement.packet_command in ACKED_COMMANDS
                        and measurement.packet_sequence is not None
                    ):
                        acked = await self.client.send_frames(
                            build_reply_frames(
                                pkg_index=self.client.next_pkg_index(),
                                reply_index=measurement.packet_sequence,
                            )
                        )
                        _LOGGER.debug(
                            "Atflee ack %s: cmd=0x%02X reply_index=%s",
                            "sent" if acked else "failed",
                            measurement.packet_command,
                            measurement.packet_sequence,
                        )

                    if measurement.measure_state == "handshake":
                        continue

                    user_id = self._resolve_user(measurement)
                    self._apply_body_composition(measurement, user_id)

                    # Ignore control/heartbeat packets that do not carry any mapped value.
                    # Example: 001a010000... (frequently interleaved with stable A3).
                    if (
                        measurement.weight_kg is None
                        and measurement.bmi is None
                        and measurement.body_fat_pct is None
                        and measurement.impedance_ohm is None
                        and measurement.battery_pct is None
                        and measurement.verify_status is None
                        and measurement.measure_status is None
                        and measurement.scale_status is None
                        and measurement.heart_rate is None
                        and measurement.measure_state is None
                        and measurement.subcutaneous_fat_pct is None
                        and measurement.visceral_fat is None
                        and measurement.muscle_pct is None
                        and measurement.muscle_mass is None
                        and measurement.bmr is None
                        and measurement.bone_mass is None
                        and measurement.moisture_pct is None
                        and measurement.protein_pct is None
                        and measurement.skeletal_muscle_pct is None
                        and measurement.physical_age is None
                        and measurement.body_score is None
                    ):
                        _LOGGER.debug(
                            "Atflee packet ignored (no mapped measurement fields): raw=%s",
                            measurement.raw_hex,
                        )
                        continue

                    measurement = self._merge_with_previous_measurement(measurement, user_id)

                    profile = self._profile(user_id)
                    if profile and measurement.bmi is None and measurement.weight_kg is not None:
                        height_m = profile[0] / 100.0
                        measurement.bmi = round(measurement.weight_kg / (height_m * height_m), 2)

                    self.async_set_updated_data(
                        self._build_state(
                            measurement=measurement,
                            user_id=user_id,
                            connected=True,
                            measuring=not measurement.is_body_composition_complete,
                        )
                    )
            except TimeoutError as err:
                if connected and measure_started is not None:
                    # Normal end: measured then went idle. Keep this wake
                    # "handled" so we don't immediately re-measure while still
                    # advertising.
                    _LOGGER.debug("Atflee session idle timeout for %s", self.address)
                else:
                    # Timed out before the link was up, or before measuring
                    # started: a failure, not an idle end. Allow a retry once
                    # the cooldown elapses.
                    outcome = err
                    self._handled_current_presence = False
                    if connected:
                        trace.fail(ARM)
                    _LOGGER.debug("Atflee session timed out for %s: %s", self.address, err)
            except asyncio.CancelledError:
                cancelled = True
                raise
            except Exception as err:  # noqa: BLE001
                # Abnormal end (connect/notify failure): allow a retry on the
                # next watchdog tick once the cooldown elapses.
                outcome = err
                self._handled_current_presence = False
                if connected:
                    trace.fail(ARM if measure_started is None else MEASURE)
                _LOGGER.debug("Atflee session failed for %s: %s", self.address, err)
            finally:
                # Bounded so a stuck BLE peer never pins this task in the
                # "running" state and blocks future advertisement triggers.
                try:
                    await asyncio.wait_for(self.client.disconnect(), timeout=8.0)
                except asyncio.TimeoutError:
                    _LOGGER.debug(
                        "Atflee disconnect exceeded outer budget for %s; forcing teardown",
                        self.address,
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug(
                        "Atflee disconnect raised for %s: %s",
                        self.address,
                        err,
                    )
                self._last_session_end_monotonic = monotonic()
                _LOGGER.debug(
                    "Atflee session end: address=%s session=#%d adv_count=%d "
                    "cooldown_starts=%.1fs",
                    self.address,
                    self._session_trigger_count,
                    self._adv_callback_count,
                    self._reconnect_cooldown_seconds,
                )
                if measure_started is not None:
                    trace.record(MEASURE, monotonic() - measure_started)
                elif arm_started is not None:
                    trace.record(ARM, monotonic() - arm_started)
                trace.note(packets=packets)
                if not cancelled:
                    self.session_report_pending = False
                    if not (outcome is not None and self._failure_recorded_this_wake):
                        try:
                            try:
                                report = build_session_report(
                                    self.hass,
                                    self.address,
                                    operation="measure",
                                    trace=trace,
                                    exc=outcome,
                                )
                            except Exception as report_err:  # noqa: BLE001
                                # Diagnostics must not mask the session's own outcome.
                                _LOGGER.debug(
                                    "Building the session report failed: %s", report_err
                                )
                                report = fallback_report(
                                    "measure", trace=trace, exc=outcome
                                )
                            self.session_reports.record(report)
                            if outcome is not None:
                                self._failure_recorded_this_wake = True
                        except Exception:  # noqa: BLE001 - diagnostics must never break a session
                            _LOGGER.debug("Atflee session report failed for %s", self.address)
                self.async_set_updated_data(self._build_state(connected=False, measuring=False))

    async def _async_update_data(self) -> AtfleeState:
        # Initial state only. Real updates come from advertisement callback sessions.
        if self._adv_unsub is None:
            raise UpdateFailed("Advertisement callback not initialized")
        return self._build_state(connected=False, measuring=False)
