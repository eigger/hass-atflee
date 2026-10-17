"""Real HA config entries and deterministic external Bluetooth transport."""

from time import monotonic
from types import SimpleNamespace

import pytest
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from habluetooth import get_manager
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigSubentry
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.atflee.const import DOMAIN

ADDRESS = "AA:BB:CC:DD:EE:FF"


class ScaleTransport:
    """Only replace the remote GATT link, leaving the integration client real."""

    def __init__(self):
        self.is_connected = False
        self.services = SimpleNamespace(services={}, get_characteristic=lambda _: None)
        self.connections = 0
        self.disconnects = 0
        self.writes = []
        self.callbacks = {}
        self.fail_connect = False

    async def connect(self, **kwargs):
        if self.fail_connect:
            raise TimeoutError("scale unavailable")
        self.connections += 1
        self.is_connected = True
        return self

    async def disconnect(self):
        self.disconnects += 1
        self.is_connected = False

    async def start_notify(self, uuid, callback):
        self.callbacks[uuid] = callback

    async def stop_notify(self, uuid):
        self.callbacks.pop(uuid, None)

    async def write_gatt_char(self, uuid, data, response=False):
        self.writes.append((uuid, bytes(data), response))

    def push(self, data):
        for callback in tuple(self.callbacks.values()):
            callback(
                SimpleNamespace(uuid="0000ffb2-0000-1000-8000-00805f9b34fb"),
                bytearray(data),
            )


class Services:
    services = {}

    def __iter__(self):
        return iter(())

    def get_characteristic(self, _uuid):
        return None


@pytest.fixture
def transport(monkeypatch):
    device = ScaleTransport()
    device.services = Services()
    monkeypatch.setattr(
        "custom_components.atflee.atflee_ble.connection.establish_connection",
        device.connect,
    )
    return device


@pytest.fixture
async def bluetooth_ready(hass, enable_bluetooth):
    assert await async_setup_component(hass, "bluetooth", {})
    return get_manager()


@pytest.fixture
async def advertisement(hass, bluetooth_ready):
    device = BLEDevice(ADDRESS, "iGripX_TEST", {})
    data = AdvertisementData(
        local_name="iGripX_TEST",
        manufacturer_data={},
        service_data={},
        service_uuids=["0000ffb0-0000-1000-8000-00805f9b34fb"],
        tx_power=None,
        rssi=-55,
        platform_data=(),
    )
    info = BluetoothServiceInfoBleak.from_scan(
        "00:00:00:00:00:01", device, data, monotonic(), True
    )
    bluetooth_ready.scanner_adv_received(info)
    await hass.async_block_till_done()
    return info


@pytest.fixture
def entry(hass):
    config = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        title="Test scale",
        data={
            "address": ADDRESS,
            "notify_timeout_seconds": 3,
            "enable_body_composition": False,
        },
    )
    config.add_to_hass(hass)
    for sid, name, slot, weight in [
        ("user_one", "Test One", 1, 60.0),
        ("user_two", "Test Two", 2, 80.0),
    ]:
        hass.config_entries.async_add_subentry(
            config,
            ConfigSubentry(
                subentry_id=sid,
                subentry_type="user",
                title=name,
                unique_id=None,
                data={
                    "name": name,
                    "slot": slot,
                    "height_cm": 170,
                    "birth_date": "1990-01-01",
                    "sex": "male",
                    "expected_weight_kg": weight,
                },
            ),
        )
    return config


@pytest.fixture
async def loaded_entry(hass, entry, transport, bluetooth_ready):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
