"""Shared device info for the scale and its users."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_USER_NAME, DOMAIN
from .user_profile import user_device_identifier


def scale_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Device of the scale itself (battery, connection, diagnostics)."""
    address = entry.data[CONF_ADDRESS]
    return DeviceInfo(
        connections={(CONNECTION_BLUETOOTH, address)},
        identifiers={(DOMAIN, address)},
        name=entry.title,
        manufacturer="Atflee",
        model="BLE Scale",
    )


def user_device_info(entry: ConfigEntry, subentry: ConfigSubentry) -> DeviceInfo:
    """Device of one scale user, attached to the scale device."""
    address = entry.data[CONF_ADDRESS]
    return DeviceInfo(
        identifiers={(DOMAIN, user_device_identifier(address, subentry.subentry_id))},
        name=str(subentry.data.get(CONF_USER_NAME) or subentry.title),
        manufacturer="Atflee",
        model="Scale user",
        via_device=(DOMAIN, address),
    )
