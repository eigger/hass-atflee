"""Data coordinator for the Atflee integration."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from time import monotonic

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .atflee_ble.connection import AtfleeBleClient
from .const import (
    CONF_HEIGHT_CM,
    CONF_NOTIFY_TIMEOUT_SECONDS,
    DEFAULT_HEIGHT_CM,
    DOMAIN,
    GATT_PROFILES,
)
from .atflee_ble.models import AtfleeMeasurement, AtfleeState

_LOGGER = logging.getLogger(__name__)


class AtfleeDataUpdateCoordinator(DataUpdateCoordinator[AtfleeState]):
    """Coordinate BLE updates for one Atflee scale.

    Flow:
    1) Wait for advertisement callback from HA bluetooth.
    2) Open one GATT session, subscribe notify.
    3) Keep session while notifications keep arriving.
    4) Disconnect when idle timeout passes without packet.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.address: str = entry.data[CONF_ADDRESS]
        self.client = AtfleeBleClient(hass, self.address)
        self._adv_unsub = None
        self._session_task: asyncio.Task | None = None
        self._session_lock = asyncio.Lock()
        self._connected_started_monotonic: float | None = None
        self._last_session_end_monotonic: float = 0.0
        self._reconnect_cooldown_seconds: float = 5.0

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.address}",
            update_interval=None,
        )

    async def async_start(self) -> None:
        """Start advertisement-driven update flow."""
        if self._adv_unsub is not None:
            return
        self._adv_unsub = bluetooth.async_register_callback(
            self.hass,
            self._async_on_advertisement,
            {"address": self.address},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
        _LOGGER.debug("Atflee adv callback registered for %s", self.address)

    async def async_stop(self) -> None:
        """Stop callbacks and running session."""
        if self._adv_unsub is not None:
            self._adv_unsub()
            self._adv_unsub = None
        if self._session_task is not None and not self._session_task.done():
            self._session_task.cancel()
            try:
                await self._session_task
            except asyncio.CancelledError:
                pass
        await self.client.disconnect()

    @callback
    def _async_on_advertisement(self, _service_info, _change) -> None:
        """Start one session when advertisement is received."""
        _LOGGER.debug("Atflee advertisement received for %s", self.address)
        now = monotonic()
        remaining_cooldown = self._reconnect_cooldown_seconds - (
            now - self._last_session_end_monotonic
        )
        if remaining_cooldown > 0:
            _LOGGER.debug(
                "Atflee reconnect cooldown active for %s: %.2fs remaining",
                self.address,
                remaining_cooldown,
            )
            return
        if self._session_task is not None and not self._session_task.done():
            _LOGGER.debug("Atflee session already running; skipping new trigger")
            return
        self._session_task = self.hass.async_create_task(self._run_measurement_session())

    def _current_height_cm(self) -> int:
        return int(
            self.entry.options.get(
                CONF_HEIGHT_CM,
                self.entry.data.get(CONF_HEIGHT_CM, DEFAULT_HEIGHT_CM),
            )
        )

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
        measurement=None,
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

        return AtfleeState(
            measurement=measurement if measurement is not None else (prev.measurement if prev else None),
            last_packet_hex=measurement.raw_hex if measurement is not None else (prev.last_packet_hex if prev else None),
            user_height_cm=self._current_height_cm(),
            connected=connected,
            measuring=measuring,
            connection_started_at=connection_started_at,
            connection_duration_seconds=duration_seconds,
            updated_at=now,
        )

    def _merge_with_previous_measurement(self, measurement: AtfleeMeasurement) -> AtfleeMeasurement:
        """Preserve last known sensor values when control packets omit them."""
        prev = self.data if isinstance(self.data, AtfleeState) else None
        prev_measurement = prev.measurement if prev else None
        if prev_measurement is None:
            return measurement

        # 기본 체중/체성분
        if measurement.weight_kg is None:
            measurement.weight_kg = prev_measurement.weight_kg
        if measurement.weight_lb is None:
            measurement.weight_lb = prev_measurement.weight_lb
        if measurement.weight_st is None:
            measurement.weight_st = prev_measurement.weight_st
        if measurement.bmi is None:
            measurement.bmi = prev_measurement.bmi
        if measurement.body_fat_pct is None:
            measurement.body_fat_pct = prev_measurement.body_fat_pct
        if measurement.impedance_ohm is None:
            measurement.impedance_ohm = prev_measurement.impedance_ohm
        if measurement.battery_pct is None:
            measurement.battery_pct = prev_measurement.battery_pct
        # 확장 체성분
        if measurement.subcutaneous_fat_pct is None:
            measurement.subcutaneous_fat_pct = prev_measurement.subcutaneous_fat_pct
        if measurement.visceral_fat is None:
            measurement.visceral_fat = prev_measurement.visceral_fat
        if measurement.muscle_pct is None:
            measurement.muscle_pct = prev_measurement.muscle_pct
        if measurement.muscle_mass is None:
            measurement.muscle_mass = prev_measurement.muscle_mass
        if measurement.bmr is None:
            measurement.bmr = prev_measurement.bmr
        if measurement.bone_mass is None:
            measurement.bone_mass = prev_measurement.bone_mass
        if measurement.moisture_pct is None:
            measurement.moisture_pct = prev_measurement.moisture_pct
        if measurement.protein_pct is None:
            measurement.protein_pct = prev_measurement.protein_pct
        if measurement.skeletal_muscle_pct is None:
            measurement.skeletal_muscle_pct = prev_measurement.skeletal_muscle_pct
        if measurement.physical_age is None:
            measurement.physical_age = prev_measurement.physical_age
        if measurement.body_score is None:
            measurement.body_score = prev_measurement.body_score

        return measurement

    async def _run_measurement_session(self) -> None:
        """Run one connect/notify session triggered by advertisement."""
        async with self._session_lock:
            ble_device = bluetooth.async_ble_device_from_address(self.hass, self.address)
            if ble_device is None:
                _LOGGER.debug("Adv trigger but BLE device unavailable: %s", self.address)
                return
            _LOGGER.debug(
                "Atflee session start: address=%s name=%s rssi=%s",
                self.address,
                ble_device.name,
                getattr(ble_device, "rssi", None),
            )

            idle_timeout = self._idle_timeout_seconds()
            try:
                await self.client.connect_with_profiles(
                    ble_device=ble_device,
                    profiles=GATT_PROFILES,
                )
                _LOGGER.debug(
                    "Atflee session connected: address=%s idle_timeout=%.1fs",
                    self.address,
                    idle_timeout,
                )
                
                # Active Trigger: Send User Info Packet (B1) for Body Composition
                from .atflee_ble.protocol import build_user_info_packet
                from .const import (
                    CONF_BIRTH_YEAR,
                    CONF_SEX,
                    CONF_ENABLE_BODY_COMP,
                    DEFAULT_BIRTH_YEAR,
                    DEFAULT_SEX,
                    DEFAULT_ENABLE_BODY_COMP,
                )
                
                send_enabled = bool(self.entry.options.get(CONF_ENABLE_BODY_COMP, self.entry.data.get(CONF_ENABLE_BODY_COMP, DEFAULT_ENABLE_BODY_COMP)))
                
                if send_enabled:
                    birth_year = int(self.entry.options.get(CONF_BIRTH_YEAR, self.entry.data.get(CONF_BIRTH_YEAR, DEFAULT_BIRTH_YEAR)))
                    current_year = datetime.now().year
                    age = max(1, current_year - birth_year)
                    
                    sex = str(self.entry.options.get(CONF_SEX, self.entry.data.get(CONF_SEX, DEFAULT_SEX)))
                    height_cm = self._current_height_cm()
                    user_index = 1
                    
                    b1_packet = build_user_info_packet(
                        user_index=user_index,
                        sex=sex,
                        age=age,
                        height_cm=height_cm
                    )
                    await self.client.send_user_info(b1_packet)
                else:
                    _LOGGER.debug("Atflee body composition measurement skipped (disabled)")

                self.async_set_updated_data(self._build_state(connected=True, measuring=True))

                last_event = monotonic()
                while True:
                    remaining = idle_timeout - (monotonic() - last_event)
                    if remaining <= 0:
                        break
                    measurement = await self.client.wait_for_measurement(timeout_seconds=remaining)
                    last_event = monotonic()
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

                    measurement = self._merge_with_previous_measurement(measurement)

                    height_cm = self._current_height_cm()
                    if measurement.bmi is None and measurement.weight_kg is not None and height_cm > 0:
                        height_m = height_cm / 100.0
                        measurement.bmi = round(measurement.weight_kg / (height_m * height_m), 2)

                    self.async_set_updated_data(
                        self._build_state(
                            measurement=measurement,
                            connected=True,
                            measuring=not measurement.is_body_composition_complete,
                        )
                    )
            except TimeoutError:
                _LOGGER.debug("Atflee session idle timeout for %s", self.address)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Atflee session failed for %s: %s", self.address, err)
            finally:
                await self.client.disconnect()
                self._last_session_end_monotonic = monotonic()
                _LOGGER.debug("Atflee session end: address=%s", self.address)
                self.async_set_updated_data(self._build_state(connected=False, measuring=False))

    async def _async_update_data(self) -> AtfleeState:
        # Initial state only. Real updates come from advertisement callback sessions.
        if self._adv_unsub is None:
            raise UpdateFailed("Advertisement callback not initialized")
        return self._build_state(connected=False, measuring=False)
