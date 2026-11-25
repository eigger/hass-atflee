"""Device fields are built once and passed as keyword arguments."""

from __future__ import annotations

from types import SimpleNamespace

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo

from custom_components.atflee.atflee_ble.models import AtfleeHardwareInfo
from custom_components.atflee.entity import scale_device_fields, scale_device_info

ADDRESS = "AA:BB:CC:DD:EE:FF"
BASE = {
    "connections": {(CONNECTION_BLUETOOTH, ADDRESS)},
    "identifiers": {("atflee", ADDRESS)},
    "name": "Scale",
    "manufacturer": "Atflee",
    "model": "BLE Scale",
}


def _entry(hardware=None, *, runtime=True):
    entry = SimpleNamespace(data={"address": ADDRESS}, title="Scale")
    if runtime:
        entry.runtime_data = SimpleNamespace(hardware_info=hardware)
    return entry


def test_scale_fields_without_hardware_info() -> None:
    assert scale_device_fields(_entry()) == BASE
    assert scale_device_fields(_entry(runtime=False)) == BASE
    assert scale_device_fields(_entry(AtfleeHardwareInfo())) == BASE


def test_scale_fields_with_hardware_info() -> None:
    hardware = AtfleeHardwareInfo(
        manufacturer="Maker",
        model="JC780",
        serial_number="123",
        hardware_revision="H1",
        firmware_revision="F2",
    )
    assert scale_device_fields(_entry(hardware)) == {
        **BASE,
        "model": "JC780",
        "serial_number": "123",
        "hw_version": "H1",
        "sw_version": "F2",
    }
    only_sw = AtfleeHardwareInfo(software_revision="S3")
    assert scale_device_fields(_entry(only_sw)) == {**BASE, "sw_version": "S3"}


def test_scale_info_matches_fields() -> None:
    hardware = AtfleeHardwareInfo(model="JC780", serial_number="123")
    entry = _entry(hardware)
    fields = scale_device_fields(entry)
    info = scale_device_info(entry)
    assert info == DeviceInfo(**fields)
    # Fields are fresh each call, so callers cannot mutate shared state.
    assert scale_device_fields(entry) is not fields


async def test_scale_device_registered_with_fields(hass, loaded_entry) -> None:
    from homeassistant.helpers import device_registry as dr

    from custom_components.atflee.registry_compat import find_device

    device = find_device(dr.async_get(hass), ("atflee", ADDRESS), loaded_entry.entry_id)
    assert device is not None
    assert device.connections == {(CONNECTION_BLUETOOTH, ADDRESS)}
    assert device.manufacturer == "Atflee"
    assert device.name == loaded_entry.title
    assert device.model == "BLE Scale"
