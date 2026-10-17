"""Tests for the device registry version helpers (no Home Assistant)."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types
from typing import TypedDict

# Load the pure modules without running the integration package (it needs Home Assistant).
_DIR = Path(__file__).parents[1] / "custom_components" / "atflee"
_PKG = types.ModuleType("atflee_pure_rc")
_PKG.__path__ = [str(_DIR)]
sys.modules["atflee_pure_rc"] = _PKG

rc = importlib.import_module("atflee_pure_rc.registry_compat")

SCALE = ("atflee", "AA:BB:CC:DD:EE:FF")


class OldDeviceInfo(TypedDict, total=False):
    """DeviceInfo before 2026.8: only via_device."""

    identifiers: set[tuple[str, str]]
    via_device: tuple[str, str]


class NewDeviceInfo(TypedDict, total=False):
    """DeviceInfo from 2026.8: via_device_id added."""

    identifiers: set[tuple[str, str]]
    via_device: tuple[str, str]
    via_device_id: str


class DataclassDeviceInfo:
    """Later cores: a dataclass that still exposes TypedDict key sets."""

    __required_keys__ = frozenset()
    __optional_keys__ = frozenset({"identifiers", "via_device_id"})


def test_old_core_uses_via_device() -> None:
    assert not rc.supports_via_device_id(OldDeviceInfo)
    assert rc.via_device_fields(OldDeviceInfo, SCALE, "dev1") == {"via_device": SCALE}


def test_new_core_uses_via_device_id() -> None:
    for cls in (NewDeviceInfo, DataclassDeviceInfo):
        assert rc.supports_via_device_id(cls)
        assert rc.via_device_fields(cls, SCALE, "dev1") == {"via_device_id": "dev1"}


def test_new_core_without_registered_parent_falls_back() -> None:
    assert rc.via_device_fields(NewDeviceInfo, SCALE, None) == {"via_device": SCALE}


class OldRegistry:
    def __init__(self) -> None:
        self.calls: list = []

    def async_get_device(self, identifiers=None, connections=None):
        self.calls.append(identifiers)
        return "device"


class NewRegistry(OldRegistry):
    def async_get_device_by_identifier(self, identifier, config_entry_id):
        self.calls.append((identifier, config_entry_id))
        return "scoped"


def test_find_device_old_core() -> None:
    registry = OldRegistry()
    assert rc.find_device(registry, SCALE, "entry") == "device"
    assert registry.calls == [{SCALE}]


def test_find_device_new_core_is_scoped_to_entry() -> None:
    registry = NewRegistry()
    assert rc.find_device(registry, SCALE, "entry") == "scoped"
    assert registry.calls == [(SCALE, "entry")]
