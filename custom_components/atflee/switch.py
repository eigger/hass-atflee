"""Switch platform for Atflee integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ENABLE_BODY_COMP,
    DEFAULT_ENABLE_BODY_COMP,
    DOMAIN,
)
from .coordinator import AtfleeDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Atflee switch entities."""
    coordinator: AtfleeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AtfleeBodyCompSwitch(coordinator, entry)])


class AtfleeBodyCompSwitch(SwitchEntity):
    """Switch to enable/disable body composition measurement."""

    _attr_has_entity_name = True
    _attr_translation_key = "enable_body_comp"
    _attr_icon = "mdi:human-pregnant"  # Or something related to body composition

    def __init__(self, coordinator: AtfleeDataUpdateCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_enable_body_composition"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, address)},
            identifiers={(DOMAIN, address)},
            name=entry.title,
            manufacturer="Atflee",
            model="BLE Scale",
        )

    @property
    def is_on(self) -> bool:
        """Return true if body composition measurement is enabled."""
        return bool(
            self._entry.options.get(
                CONF_ENABLE_BODY_COMP,
                self._entry.data.get(CONF_ENABLE_BODY_COMP, DEFAULT_ENABLE_BODY_COMP),
            )
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable body composition measurement."""
        await self._async_set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable body composition measurement."""
        await self._async_set_state(False)

    async def _async_set_state(self, enabled: bool) -> None:
        """Update the configuration option."""
        options = dict(self._entry.options)
        options[CONF_ENABLE_BODY_COMP] = enabled
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        self.async_write_ha_state()
