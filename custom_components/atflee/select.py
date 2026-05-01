"""Select platform for Atflee integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_SEX,
    DEFAULT_SEX,
    DOMAIN,
)
from .coordinator import AtfleeDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Atflee select entities."""
    coordinator: AtfleeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AtfleeSexSelectEntity(coordinator, entry)])


class AtfleeSexSelectEntity(SelectEntity):
    """Configurable user sex used for body metrics."""

    _attr_has_entity_name = True
    _attr_options = ["male", "female"]
    _attr_translation_key = "sex"
    _attr_icon = "mdi:gender-male-female"

    def __init__(self, coordinator: AtfleeDataUpdateCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_sex"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, address)},
            identifiers={(DOMAIN, address)},
            name=entry.title,
            manufacturer="Atflee",
            model="BLE Scale",
        )

    @property
    def current_option(self) -> str:
        """Return current sex."""
        return str(
            self._entry.options.get(
                CONF_SEX,
                self._entry.data.get(CONF_SEX, DEFAULT_SEX),
            )
        )

    async def async_select_option(self, option: str) -> None:
        """Update user sex."""
        options = dict(self._entry.options)
        options[CONF_SEX] = option
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        await self._coordinator.async_request_refresh()
        self.async_write_ha_state()
