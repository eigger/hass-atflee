"""Number platform for Atflee integration."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_HEIGHT_CM,
    CONF_BIRTH_YEAR,
    DEFAULT_HEIGHT_CM,
    DEFAULT_BIRTH_YEAR,
    DOMAIN,
    MAX_HEIGHT_CM,
    MIN_HEIGHT_CM,
    MIN_BIRTH_YEAR,
    MAX_BIRTH_YEAR,
)
from .coordinator import AtfleeDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Atflee number entities."""
    coordinator: AtfleeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        AtfleeHeightNumberEntity(coordinator, entry),
        AtfleeBirthYearNumberEntity(coordinator, entry),
    ])


class AtfleeHeightNumberEntity(NumberEntity):
    """Configurable user height used for derived body metrics."""

    _attr_has_entity_name = True
    _attr_translation_key = "height_cm"
    _attr_icon = "mdi:human-male-height"
    _attr_device_class = NumberDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.CENTIMETERS
    _attr_native_step = 1
    _attr_native_min_value = MIN_HEIGHT_CM
    _attr_native_max_value = MAX_HEIGHT_CM
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: AtfleeDataUpdateCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_height_cm"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, address)},
            identifiers={(DOMAIN, address)},
            name=entry.title,
            manufacturer="Atflee",
            model="BLE Scale",
        )

    @property
    def native_value(self) -> float:
        """Return configured user height in cm."""
        return float(
            self._entry.options.get(
                CONF_HEIGHT_CM,
                self._entry.data.get(CONF_HEIGHT_CM, DEFAULT_HEIGHT_CM),
            )
        )

    async def async_set_native_value(self, value: float) -> None:
        """Persist user height as config entry option."""
        height_cm = int(round(value))
        if height_cm < MIN_HEIGHT_CM:
            height_cm = MIN_HEIGHT_CM
        if height_cm > MAX_HEIGHT_CM:
            height_cm = MAX_HEIGHT_CM

        options = dict(self._entry.options)
        options[CONF_HEIGHT_CM] = height_cm
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        await self._coordinator.async_request_refresh()
        self.async_write_ha_state()


class AtfleeBirthYearNumberEntity(NumberEntity):
    """Configurable user birth year used for age calculation."""

    _attr_has_entity_name = True
    _attr_translation_key = "birth_year"
    _attr_icon = "mdi:calendar-range"
    _attr_native_step = 1
    _attr_native_min_value = MIN_BIRTH_YEAR
    _attr_native_max_value = MAX_BIRTH_YEAR
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: AtfleeDataUpdateCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_birth_year"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, address)},
            identifiers={(DOMAIN, address)},
            name=entry.title,
            manufacturer="Atflee",
            model="BLE Scale",
        )

    @property
    def native_value(self) -> float:
        """Return configured user birth year."""
        return float(
            self._entry.options.get(
                CONF_BIRTH_YEAR,
                self._entry.data.get(CONF_BIRTH_YEAR, DEFAULT_BIRTH_YEAR),
            )
        )

    async def async_set_native_value(self, value: float) -> None:
        """Persist user birth year as config entry option."""
        birth_year = int(round(value))
        if birth_year < MIN_BIRTH_YEAR:
            birth_year = MIN_BIRTH_YEAR
        if birth_year > MAX_BIRTH_YEAR:
            birth_year = MAX_BIRTH_YEAR

        options = dict(self._entry.options)
        options[CONF_BIRTH_YEAR] = birth_year
        self.hass.config_entries.async_update_entry(self._entry, options=options)
        await self._coordinator.async_request_refresh()
        self.async_write_ha_state()
