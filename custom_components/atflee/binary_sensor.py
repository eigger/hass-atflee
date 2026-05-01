"""Binary sensor platform for Atflee integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AtfleeDataUpdateCoordinator

CONNECTION_SENSOR = BinarySensorEntityDescription(
    key="ble_connection",
    translation_key="ble_connection",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Atflee binary sensors."""
    coordinator: AtfleeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AtfleeConnectionBinarySensor(coordinator, entry)])


class AtfleeConnectionBinarySensor(
    CoordinatorEntity[AtfleeDataUpdateCoordinator], BinarySensorEntity
):
    """BLE connection status binary sensor."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    entity_description = CONNECTION_SENSOR

    def __init__(self, coordinator: AtfleeDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_ble_connection"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, address)},
            identifiers={(DOMAIN, address)},
            name=entry.title,
            manufacturer="Atflee",
            model="BLE Scale",
        )

    @property
    def is_on(self) -> bool:
        """Return true when BLE session is connected."""
        return self.coordinator.data.connected

    @property
    def icon(self) -> str:
        """Return icon based on connection state."""
        return "mdi:bluetooth-connect" if self.is_on else "mdi:bluetooth-off"
