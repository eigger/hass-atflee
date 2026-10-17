"""The Atflee integration."""

from __future__ import annotations

import logging

from types import MappingProxyType

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, SUBENTRY_TYPE_USER
from .coordinator import AtfleeConfigEntry, AtfleeDataUpdateCoordinator
from .user_profile import legacy_entity_unique_ids, migrate_v1_to_v2

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


async def async_migrate_entry(hass: HomeAssistant, entry: AtfleeConfigEntry) -> bool:
    """Migrate a v1 entry (profile in options) to v2 (profile in a user subentry)."""
    if entry.version > 2:
        # Created by a newer version; cannot downgrade.
        return False

    if entry.version == 1:
        result = migrate_v1_to_v2(entry.data, entry.options, entry.title)

        # Add the subentry first: if we are interrupted before the version is
        # bumped, the next run sees the subentry and does not add a second one.
        if not any(
            sub.subentry_type == SUBENTRY_TYPE_USER
            for sub in entry.subentries.values()
        ):
            hass.config_entries.async_add_subentry(
                entry,
                ConfigSubentry(
                    data=MappingProxyType(result.user_data),
                    subentry_type=SUBENTRY_TYPE_USER,
                    title=result.user_title,
                    unique_id=None,
                ),
            )

        registry = er.async_get(hass)
        address = entry.data[CONF_ADDRESS]
        for platform, unique_id in legacy_entity_unique_ids(address):
            entity_id = registry.async_get_entity_id(platform, DOMAIN, unique_id)
            if entity_id is not None:
                registry.async_remove(entity_id)

        hass.config_entries.async_update_entry(
            entry,
            data=result.entry_data,
            options=result.entry_options,
            version=2,
        )
        _LOGGER.debug("Migrated Atflee entry %s to version 2", entry.entry_id)

    return True
