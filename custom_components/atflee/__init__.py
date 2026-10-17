"""The Atflee integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store

from .coordinator import (
    AtfleeConfigEntry,
    AtfleeDataUpdateCoordinator,
    last_weights_store_key,
)
from .const import (
    CONF_DEFAULT_USER,
    CONF_ENABLE_BODY_COMP,
    CONF_FALLBACK_MAX_DELTA_KG,
    CONF_MATCH_TOLERANCE_KG,
    LAST_WEIGHTS_STORE_VERSION,
)
from .entity import scale_device_info
from .user_profile import reload_needed

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
]

# Options the coordinator reads at use time, so changing them needs no reload.
LIVE_OPTION_KEYS = (
    CONF_ENABLE_BODY_COMP,
    CONF_DEFAULT_USER,
    CONF_MATCH_TOLERANCE_KG,
    CONF_FALLBACK_MAX_DELTA_KG,
)


async def async_setup_entry(hass: HomeAssistant, entry: AtfleeConfigEntry) -> bool:
    """Set up Atflee from a config entry."""
    coordinator = AtfleeDataUpdateCoordinator(hass, entry)
    # Register cleanup before acquiring callbacks, including partial startup.
    entry.async_on_unload(coordinator.async_stop)
    forwarding_started = False
    try:
        await coordinator.async_load_last_weights()
        await coordinator.async_start()
        await coordinator.async_config_entry_first_refresh()
        if coordinator.last_update_success is False:
            raise ConfigEntryNotReady("Initial BLE update failed")

        entry.runtime_data = coordinator

        # User devices point at the scale device by its registry id, so make sure
        # it exists before any platform adds entities.
        scale_device = dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id, **scale_device_info(entry)
        )
        coordinator.scale_device_id = scale_device.id

        # Entities are created per user subentry, so adding, removing or editing a
        # user needs a reload, as does any option except the body composition
        # switch, the default user and the identification thresholds, which the
        # coordinator reads live.
        users = _users_snapshot(coordinator)
        options = {**entry.data, **entry.options}

        async def _async_entry_updated(
            hass: HomeAssistant, entry: AtfleeConfigEntry
        ) -> None:
            if reload_needed(
                users,
                _users_snapshot(entry.runtime_data),
                options,
                {**entry.data, **entry.options},
                LIVE_OPTION_KEYS,
            ):
                await hass.config_entries.async_reload(entry.entry_id)

        forwarding_started = True
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
        _LOGGER.debug("Atflee entry setup complete: %s", entry.entry_id)
        return True

    except BaseException:
        try:
            if forwarding_started:
                await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        finally:
            await coordinator.async_stop()
        raise


def _users_snapshot(coordinator: AtfleeDataUpdateCoordinator) -> dict[str, tuple]:
    """Return what the per-user entities and devices are built from."""
    return {
        sid: (sub.title, dict(sub.data))
        for sid, sub in coordinator.user_subentries().items()
    }


async def async_unload_entry(hass: HomeAssistant, entry: AtfleeConfigEntry) -> bool:
    """Unload an Atflee config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        # Stop the session and BLE callbacks first (HA only runs the on_unload
        # stop after this returns), so no packet can schedule another save; then
        # write pending weights, which also cancels a delayed save. Otherwise a
        # save could recreate the file after removal or a reload miss the newest
        # weight.
        await entry.runtime_data.async_stop()
        await entry.runtime_data.async_flush_last_weights()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: AtfleeConfigEntry) -> None:
    """Delete the stored last weights together with the config entry."""
    await Store(
        hass, LAST_WEIGHTS_STORE_VERSION, last_weights_store_key(entry.entry_id)
    ).async_remove()
