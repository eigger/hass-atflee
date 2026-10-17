"""The Atflee integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .coordinator import AtfleeConfigEntry, AtfleeDataUpdateCoordinator
from .entity import scale_device_info

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

    # User devices point at the scale device through via_device, so make sure
    # it exists before any platform adds entities.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **scale_device_info(entry)
    )

    # Entities are created per user subentry, so adding, removing or editing a
    # user needs a reload. Other entry updates (e.g. the body composition
    # switch rewriting the options) must not reload.
    users = _users_snapshot(coordinator)

    async def _async_users_changed(hass: HomeAssistant, entry: AtfleeConfigEntry) -> None:
        if _users_snapshot(entry.runtime_data) != users:
            await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_async_users_changed))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Atflee entry setup complete: %s", entry.entry_id)
    return True


def _users_snapshot(coordinator: AtfleeDataUpdateCoordinator) -> dict[str, tuple]:
    """Return what the per-user entities and devices are built from."""
    return {
        sid: (sub.title, dict(sub.data))
        for sid, sub in coordinator.user_subentries().items()
    }


async def async_unload_entry(hass: HomeAssistant, entry: AtfleeConfigEntry) -> bool:
    """Unload an Atflee config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

