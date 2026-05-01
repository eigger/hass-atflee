"""BLE connection helpers for Atflee BLE core."""

from __future__ import annotations

from asyncio import Queue, TimeoutError, wait_for
import logging

from bleak.backends.device import BLEDevice
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_last_service_info,
)
from homeassistant.core import HomeAssistant

from ..const import DEBUG_READ_UUIDS, OPTIONAL_NOTIFY_UUIDS
from .models import AtfleeMeasurement
from .protocol import parse_measurement_packet

_LOGGER = logging.getLogger(__name__)


def _is_notify_like(properties: list[str] | tuple[str, ...] | set[str]) -> bool:
    return "notify" in properties or "indicate" in properties


class AtfleeBleClient:
    """Session-based BLE client wrapper using HA's Bluetooth stack."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self._hass = hass
        self._address = address
        self._client: BleakClientWithServiceCache | None = None
        self._notify_char_uuid: str | None = None
        self._write_char_uuid: str | None = None
        self._extra_notify_char_uuids: list[str] = []
        self._packet_queue: Queue[bytes] = Queue(maxsize=30)
        self._last_notify_packet: bytes | None = None

    async def _debug_dump_gatt_map(self, client: BleakClientWithServiceCache) -> None:
        """Dump full service/characteristic map for diagnostic purposes."""
        if not client.services:
            _LOGGER.debug("Atflee GATT map unavailable: no services cache")
            return
        for service in client.services:
            _LOGGER.debug("Atflee GATT service: uuid=%s", service.uuid)
            for char in service.characteristics:
                _LOGGER.debug(
                    "Atflee GATT char: service=%s uuid=%s props=%s",
                    service.uuid,
                    char.uuid,
                    list(char.properties),
                )

    async def _debug_probe_readable_chars(
        self, client: BleakClientWithServiceCache, target_service_uuid: str
    ) -> None:
        """Try one-shot read on readable chars for diagnostics (battery hints)."""
        if not client.services:
            return

        probes = 0
        for service in client.services:
            if service.uuid.lower() != target_service_uuid.lower():
                continue
            for char in service.characteristics:
                if "read" not in char.properties:
                    continue
                probes += 1
                if probes > 12:
                    _LOGGER.debug("Atflee readable probe limit reached")
                    return
                try:
                    data = await wait_for(client.read_gatt_char(char.uuid), timeout=2.0)
                    _LOGGER.debug(
                        "Atflee readable probe: char=%s len=%d hex=%s",
                        char.uuid,
                        len(data),
                        data.hex(),
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Atflee readable probe failed: char=%s err=%s", char.uuid, err)

    async def _debug_probe_known_read_uuids(
        self, client: BleakClientWithServiceCache, char_uuids: tuple[str, ...]
    ) -> None:
        """Probe known read UUIDs even if they are on a different service."""
        for char_uuid in char_uuids:
            try:
                data = await wait_for(client.read_gatt_char(char_uuid), timeout=2.0)
                _LOGGER.debug(
                    "Atflee known read probe: char=%s len=%d hex=%s",
                    char_uuid,
                    len(data),
                    data.hex(),
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Atflee known read probe failed: char=%s err=%s", char_uuid, err)

    @property
    def is_connected(self) -> bool:
        """Return current connection state."""
        return self._client is not None and self._client.is_connected

    def _notification_handler(self, sender: object, data: bytearray) -> None:
        packet = bytes(data)
        source = getattr(sender, "uuid", str(sender))
        _LOGGER.debug(
            "Atflee notify received: source=%s len=%d hex=%s",
            source,
            len(data),
            packet.hex(),
        )
        if self._last_notify_packet is not None and len(self._last_notify_packet) == len(packet):
            changed = [idx for idx, (a, b) in enumerate(zip(self._last_notify_packet, packet)) if a != b]
            if changed:
                preview = ",".join(str(i) for i in changed[:12])
                _LOGGER.debug(
                    "Atflee notify byte diff: source=%s changed_count=%d changed_idx=%s",
                    source,
                    len(changed),
                    preview,
                )
        self._last_notify_packet = packet
        if self._packet_queue.full():
            try:
                self._packet_queue.get_nowait()
            except Exception:  # noqa: BLE001
                pass
            _LOGGER.debug("Atflee packet queue full; dropped oldest packet")
        self._packet_queue.put_nowait(packet)
        _LOGGER.debug("Atflee packet queued: queue_size=%d", self._packet_queue.qsize())

    async def connect_with_profiles(
        self,
        ble_device: BLEDevice,
        profiles: tuple[tuple[str, str, str | None], ...],
    ) -> tuple[str, str, str | None]:
        """Try fixed GATT profiles and keep the successful session open."""

        await self.disconnect()
        while not self._packet_queue.empty():
            self._packet_queue.get_nowait()

        last_error: Exception | None = None
        for service_uuid, notify_char_uuid, write_char_uuid in profiles:
            client: BleakClientWithServiceCache | None = None
            try:
                _LOGGER.debug(
                    "Trying GATT profile service=%s notify=%s write=%s",
                    service_uuid,
                    notify_char_uuid,
                    write_char_uuid,
                )
                client = await establish_connection(
                    client_class=BleakClientWithServiceCache,
                    device=ble_device,
                    name=f"atflee-{self._address}",
                    disconnected_callback=None,
                    use_services_cache=True,
                )
                _LOGGER.debug(
                    "Atflee connected: address=%s services=%d",
                    self._address,
                    len(client.services.services) if client.services else -1,
                )
                await self._debug_dump_gatt_map(client)
                await self._debug_probe_readable_chars(client, service_uuid)
                await self._debug_probe_known_read_uuids(client, DEBUG_READ_UUIDS)

                # Some environments may carry stale/misordered profile tuples.
                # Auto-correct when notify/write UUIDs are swapped.
                resolved_notify_uuid = notify_char_uuid
                resolved_write_uuid = write_char_uuid
                if client.services and write_char_uuid:
                    notify_char = client.services.get_characteristic(notify_char_uuid)
                    write_char = client.services.get_characteristic(write_char_uuid)
                    notify_props = list(notify_char.properties) if notify_char else []
                    write_props = list(write_char.properties) if write_char else []
                    if not _is_notify_like(notify_props) and _is_notify_like(write_props):
                        _LOGGER.debug(
                            (
                                "Atflee profile auto-swap applied: "
                                "notify %s<->%s write"
                            ),
                            notify_char_uuid,
                            write_char_uuid,
                        )
                        resolved_notify_uuid = write_char_uuid
                        resolved_write_uuid = notify_char_uuid

                await client.start_notify(resolved_notify_uuid, self._notification_handler)
                notify_char = None
                if client.services:
                    notify_char = client.services.get_characteristic(resolved_notify_uuid)
                _LOGGER.debug(
                    "Atflee notify started: char=%s properties=%s",
                    resolved_notify_uuid,
                    list(notify_char.properties) if notify_char else None,
                )
                self._extra_notify_char_uuids = []
                for optional_uuid in OPTIONAL_NOTIFY_UUIDS:
                    if optional_uuid.lower() == resolved_notify_uuid.lower():
                        continue
                    optional_char = (
                        client.services.get_characteristic(optional_uuid)
                        if client.services
                        else None
                    )
                    if optional_char is None:
                        continue
                    if not (
                        "notify" in optional_char.properties
                        or "indicate" in optional_char.properties
                    ):
                        continue
                    try:
                        await client.start_notify(optional_uuid, self._notification_handler)
                        self._extra_notify_char_uuids.append(optional_uuid)
                        _LOGGER.debug(
                            "Atflee extra notify started: char=%s properties=%s",
                            optional_uuid,
                            list(optional_char.properties),
                        )
                    except Exception as err:  # noqa: BLE001
                        _LOGGER.debug(
                            "Atflee extra notify failed: char=%s err=%s",
                            optional_uuid,
                            err,
                        )
                self._client = client
                self._notify_char_uuid = resolved_notify_uuid
                self._write_char_uuid = resolved_write_uuid
                self._last_notify_packet = None
                return (service_uuid, resolved_notify_uuid, resolved_write_uuid)
            except Exception as err:  # noqa: BLE001
                last_error = err
                _LOGGER.debug("GATT profile failed: %s", err)
                if client is not None and client.is_connected:
                    await client.disconnect()
                continue

        if last_error is None:
            raise TimeoutError("No GATT profile available")
        raise last_error

    async def wait_for_measurement(self, timeout_seconds: float) -> AtfleeMeasurement:
        """Wait for one notification packet in current session."""
        _LOGGER.debug(
            "Atflee waiting packet: timeout=%.2fs queue_size=%d",
            timeout_seconds,
            self._packet_queue.qsize(),
        )
        packet = await wait_for(self._packet_queue.get(), timeout=timeout_seconds)
        _LOGGER.debug(
            "Atflee packet dequeued: len=%d hex=%s queue_size_after=%d",
            len(packet),
            packet.hex(),
            self._packet_queue.qsize(),
        )
        return parse_measurement_packet(packet)

    async def send_user_info(self, packet: bytes) -> bool:
        """Send a constructed user info packet to trigger active measurement."""
        if not self._client or not self._client.is_connected:
            _LOGGER.debug("Atflee write failed: client not connected")
            return False
        if not self._write_char_uuid:
            _LOGGER.debug("Atflee write failed: no write characteristic discovered")
            return False
            
        try:
            _LOGGER.debug("Atflee sending user info packet: len=%d hex=%s to %s", len(packet), packet.hex(), self._write_char_uuid)
            await self._client.write_gatt_char(self._write_char_uuid, packet, response=True)
            return True
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Atflee write failed: char=%s err=%s", self._write_char_uuid, err)
            # Some devices don't support write with response, retry without response
            try:
                _LOGGER.debug("Atflee retrying without response...")
                await self._client.write_gatt_char(self._write_char_uuid, packet, response=False)
                return True
            except Exception as err2:  # noqa: BLE001
                _LOGGER.debug("Atflee write without response failed: err=%s", err2)
                return False

    async def disconnect(self) -> None:
        """Stop notify and close current BLE session."""
        if self._client is None:
            return
        try:
            if self._notify_char_uuid and self._client.is_connected:
                try:
                    await self._client.stop_notify(self._notify_char_uuid)
                    _LOGGER.debug(
                        "Atflee notify stopped: char=%s",
                        self._notify_char_uuid,
                    )
                except Exception:  # noqa: BLE001
                    pass
            if self._client.is_connected and self._extra_notify_char_uuids:
                for char_uuid in self._extra_notify_char_uuids:
                    try:
                        await self._client.stop_notify(char_uuid)
                        _LOGGER.debug("Atflee extra notify stopped: char=%s", char_uuid)
                    except Exception:  # noqa: BLE001
                        pass
            if self._client.is_connected:
                await self._client.disconnect()
                _LOGGER.debug("Atflee disconnected: address=%s", self._address)
        finally:
            self._client = None
            self._notify_char_uuid = None
            self._write_char_uuid = None
            self._extra_notify_char_uuids = []
            self._last_notify_packet = None

    def last_service_info(self) -> BluetoothServiceInfoBleak | None:
        """Return latest discovery info for diagnostics."""
        return async_last_service_info(self._hass, self._address)
