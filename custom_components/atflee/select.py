"""Select platform for Atflee integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ACTIVE_USER_AUTO
from .coordinator import AtfleeConfigEntry, AtfleeDataUpdateCoordinator
from .entity import scale_device_info
from .user_profile import user_option_labels


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AtfleeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Atflee select entities."""
    async_add_entities([AtfleeActiveUserSelect(entry.runtime_data, entry)])


class AtfleeActiveUserSelect(SelectEntity):
    """Choose who steps on the scale next ("auto" = default user)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "active_user"
    _attr_icon = "mdi:account-switch"

    def __init__(
        self, coordinator: AtfleeDataUpdateCoordinator, entry: AtfleeConfigEntry
    ) -> None:
        self._coordinator = coordinator
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_active_user"
        self._attr_device_info = scale_device_info(entry)
        # Users only change through a reload, which rebuilds this entity.
        self._labels = user_option_labels(
            {sid: sub.data for sid, sub in coordinator.user_subentries().items()}
        )
        self._attr_options = [ACTIVE_USER_AUTO, *self._labels.values()]

    @property
    def current_option(self) -> str:
        """Label of the selected user, or "auto"."""
        active = self._coordinator.active_user_id
        return (
            self._labels.get(active, ACTIVE_USER_AUTO) if active else ACTIVE_USER_AUTO
        )

    async def async_added_to_hass(self) -> None:
        """Follow selection changes made by the coordinator (session end, timeout)."""
        self.async_on_remove(
            self._coordinator.async_add_active_user_listener(self.async_write_ha_state)
        )

    async def async_select_option(self, option: str) -> None:
        """Select a user by label, or auto."""
        by_label = {label: sid for sid, label in self._labels.items()}
        self._coordinator.async_set_active_user(by_label.get(option))
