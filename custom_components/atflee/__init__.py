"""The Atflee integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import AtfleeConfigEntry, AtfleeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: AtfleeConfigEntry) -> bool:
    """Set up Atflee from a config entry."""
    coordinator = AtfleeDataUpdateCoordinator(hass, entry)
    await coordinator.async_start()
    # Registered right after start so the BLE callbacks are released on every
    # exit path, including a failed first refresh (ConfigEntryNotReady retries).
    entry.async_on_unload(coordinator.async_stop)
    await coordinator.async_config_entry_first_refresh()
    if coordinator.last_update_success is False:
        raise ConfigEntryNotReady("Initial BLE update failed")

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Atflee entry setup complete: %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AtfleeConfigEntry) -> bool:
    """Unload an Atflee config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

