"""Tests for the device-info (A1) decoding and Device Information strings (no Home Assistant)."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types

# Load atflee_ble without running the integration package (it needs Home Assistant).
_BLE_DIR = Path(__file__).parents[1] / "custom_components" / "atflee" / "atflee_ble"
_PKG = types.ModuleType("atflee_ble_pure_di")
_PKG.__path__ = [str(_BLE_DIR)]
sys.modules["atflee_ble_pure_di"] = _PKG

packet = importlib.import_module("atflee_ble_pure_di.packet")
protocol = importlib.import_module("atflee_ble_pure_di.protocol")
models = importlib.import_module("atflee_ble_pure_di.models")

# Device-info frame captured from an iGripX_JC780 scale.
A1_FRAME = bytes.fromhex("000a00a1337116200019010a1900000000000018")


def _a1_message():
    message = packet.FrameAssembler().feed(A1_FRAME)
    assert message is not None
    assert message.command == packet.CMD_DEVICE_INFO
    return message


def test_captured_a1_capabilities() -> None:
    info = protocol.parse_device_info(_a1_message().data)
    assert info is not None
    assert info.electrode_count == 8
    assert info.frequency_count == 2
    assert info.impedance_count == 5
    # Matches the ten impedance shorts of this scale's stable-weight message.
    assert info.impedance_channels == 10
    assert info.impedance_scaled is True
    assert info.kg_division == 0
    assert (info.support_hr, info.support_balance, info.support_gravity) == (
        False,
        False,
        False,
    )
    assert info.function_flags == 0x01
    assert info.algorithm_type == 0x19
    assert info.raw_hex == "337116200019010a19"


def test_a1_raw_hex_round_trips() -> None:
    info = protocol.parse_device_info(_a1_message().data)
    assert protocol.parse_device_info(bytes.fromhex(info.raw_hex)) == info


def test_a1_too_short() -> None:
    assert protocol.parse_device_info(bytes(8)) is None


def test_four_electrode_counts() -> None:
    # Bit 24 clear: 4 electrodes, carry bit adds a second impedance path.
    info = protocol.parse_device_info(bytes.fromhex("20000000") + bytes(5))
    assert info.electrode_count == 4
    assert info.frequency_count == 1
    assert info.impedance_count == 2


def test_decode_gatt_string() -> None:
    assert protocol.decode_gatt_string(b"JC780") == "JC780"
    assert protocol.decode_gatt_string(b"V1.2\x00\x00\x00") == "V1.2"
    assert protocol.decode_gatt_string(b" 1.0 \r\n") == "1.0"
    assert protocol.decode_gatt_string(b"") is None
    assert protocol.decode_gatt_string(None) is None
    assert protocol.decode_gatt_string(b"\x00\x00") is None
    assert protocol.decode_gatt_string(bytearray(b"\xffA")) == "�A"


def test_hardware_info_registry_fields() -> None:
    info = models.AtfleeHardwareInfo(
        manufacturer="Maker",
        model="JC780",
        serial_number="123",
        hardware_revision="H1",
        firmware_revision="F2",
        software_revision="S3",
    )
    assert info.registry_fields() == {
        "model": "JC780",
        "serial_number": "123",
        "hw_version": "H1",
        "sw_version": "F2",
    }
    # Software revision stands in when there is no firmware revision.
    only_sw = models.AtfleeHardwareInfo(software_revision="S3")
    assert only_sw.registry_fields() == {"sw_version": "S3"}
    assert models.AtfleeHardwareInfo().registry_fields() == {}


def test_hardware_info_storage_round_trip() -> None:
    info = models.AtfleeHardwareInfo(model="JC780", firmware_revision="F2")
    stored = info.as_dict()
    assert stored == {"model": "JC780", "firmware_revision": "F2"}
    assert models.AtfleeHardwareInfo.from_dict(stored) == info


def test_hardware_info_from_bad_storage() -> None:
    cls = models.AtfleeHardwareInfo
    assert cls.from_dict(None) is None
    assert cls.from_dict("x") is None
    assert cls.from_dict({}) is None
    assert cls.from_dict({"model": "", "serial_number": 5, "other": "x"}) is None
    assert cls.from_dict({"model": "A", "serial_number": 5}) == cls(model="A")


def test_hardware_info_registry_fields_keep_brand() -> None:
    info = models.AtfleeHardwareInfo(manufacturer="Maker", model="JC780")
    assert "manufacturer" not in info.registry_fields()
    assert info.as_dict()["manufacturer"] == "Maker"
