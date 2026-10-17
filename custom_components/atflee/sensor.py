"""Sensor platform for Atflee integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigSubentry
from homeassistant.const import (
    CONF_ADDRESS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfMass,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import async_get as async_get_restore_state
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AtfleeConfigEntry, AtfleeDataUpdateCoordinator
from .entity import scale_device_info, user_device_info
from .user_profile import user_unique_id
from .atflee_ble.models import AtfleeMeasurement, AtfleeState


@dataclass(frozen=True, kw_only=True)
class AtfleeUserSensorDescription(SensorEntityDescription):
    """Description of a per-user measurement sensor."""

    value_fn: Callable[[AtfleeMeasurement], float | int | str | None]


@dataclass(frozen=True, kw_only=True)
class AtfleeScaleSensorDescription(SensorEntityDescription):
    """Description of a scale-level sensor."""

    value_fn: Callable[[AtfleeState], float | int | str | None]


# Measurements: one set per user, on that user's device.
USER_SENSORS: tuple[AtfleeUserSensorDescription, ...] = (
    AtfleeUserSensorDescription(
        key="weight",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda m: m.weight_kg,
    ),
    AtfleeUserSensorDescription(
        key="body_fat",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
        value_fn=lambda m: m.body_fat_pct,
    ),
    AtfleeUserSensorDescription(
        key="bmi",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:scale-bathroom",
        value_fn=lambda m: m.bmi,
    ),
    AtfleeUserSensorDescription(
        key="impedance",
        native_unit_of_measurement="ohm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        value_fn=lambda m: m.impedance_ohm,
    ),
    AtfleeUserSensorDescription(
        key="subcutaneous_fat",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
        value_fn=lambda m: m.subcutaneous_fat_pct,
    ),
    AtfleeUserSensorDescription(
        key="visceral_fat",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:stomach",
        value_fn=lambda m: m.visceral_fat,
    ),
    AtfleeUserSensorDescription(
        key="muscle_pct",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:arm-flex",
        value_fn=lambda m: m.muscle_pct,
    ),
    AtfleeUserSensorDescription(
        key="muscle_mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda m: m.muscle_mass,
    ),
    AtfleeUserSensorDescription(
        key="bmr",
        native_unit_of_measurement="kcal",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fire",
        value_fn=lambda m: m.bmr,
    ),
    AtfleeUserSensorDescription(
        key="bone_mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:bone",
        value_fn=lambda m: m.bone_mass,
    ),
    AtfleeUserSensorDescription(
        key="moisture_pct",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water",
        value_fn=lambda m: m.moisture_pct,
    ),
    AtfleeUserSensorDescription(
        key="protein_pct",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:food-steak",
        value_fn=lambda m: m.protein_pct,
    ),
    AtfleeUserSensorDescription(
        key="skeletal_muscle_pct",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:arm-flex-outline",
        value_fn=lambda m: m.skeletal_muscle_pct,
    ),
    AtfleeUserSensorDescription(
        key="body_fat_mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:scale-balance",
        value_fn=lambda m: m.body_fat_mass,
    ),
    AtfleeUserSensorDescription(
        key="fat_free_mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:human",
        value_fn=lambda m: m.fat_free_mass,
    ),
    AtfleeUserSensorDescription(
        key="body_water_mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water",
        value_fn=lambda m: m.body_water_mass,
    ),
    AtfleeUserSensorDescription(
        key="protein_mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:food-steak",
        value_fn=lambda m: m.protein_mass,
    ),
    AtfleeUserSensorDescription(
        key="skeletal_muscle_mass",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:arm-flex-outline",
        value_fn=lambda m: m.skeletal_muscle_mass,
    ),
    AtfleeUserSensorDescription(
        key="physical_age",
        native_unit_of_measurement="years",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:calendar-heart",
        value_fn=lambda m: m.physical_age,
    ),
    AtfleeUserSensorDescription(
        key="body_score",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:medal",
        value_fn=lambda m: m.body_score,
    ),
    AtfleeUserSensorDescription(
        key="heart_rate",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart-pulse",
        value_fn=lambda m: m.heart_rate,
    ),
)

# Scale-level state: battery and diagnostics, on the scale device.
SCALE_SENSORS: tuple[AtfleeScaleSensorDescription, ...] = (
    AtfleeScaleSensorDescription(
        key="battery",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.battery_pct,
    ),
    AtfleeScaleSensorDescription(
        key="verify_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:check-circle-outline",
        value_fn=lambda state: state.latest.verify_status if state.latest else None,
    ),
    AtfleeScaleSensorDescription(
        key="measure_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:state-machine",
        value_fn=lambda state: state.latest.measure_status if state.latest else None,
    ),
    AtfleeScaleSensorDescription(
        key="scale_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:information-outline",
        value_fn=lambda state: state.latest.scale_status if state.latest else None,
    ),
    AtfleeScaleSensorDescription(
        key="connection_duration",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer-outline",
        value_fn=lambda state: state.connection_duration_seconds,
    ),
)

# 정수 강제 변환이 필요한 키
_INT_KEYS = {
    "verify_status",
    "measure_status",
    "scale_status",
    "connection_duration",
    "battery",
    "bmr",
    "physical_age",
}


# Per-user sensors that always exist. Every other one is created the first time
# the scale (or the composition calculation) produces a value for that user, so
# values the scale never delivers do not show up as permanently unknown entities.
_ALWAYS_KEYS = frozenset({"weight", "impedance"})


def _is_customised(reg_entry: er.RegistryEntry) -> bool:
    """Return True when the user changed or disabled this registry entry."""
    return bool(
        reg_entry.disabled_by
        or reg_entry.name
        or reg_entry.icon
        or reg_entry.area_id
        or reg_entry.labels
    )


def _has_stored_value(hass: HomeAssistant, entity_id: str) -> bool:
    """Return True when the entity had a real value before the last shutdown."""
    stored = async_get_restore_state(hass).last_states.get(entity_id)
    return stored is not None and stored.state.state not in (
        STATE_UNKNOWN,
        STATE_UNAVAILABLE,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AtfleeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Atflee sensor entities."""
    coordinator = entry.runtime_data
    address = entry.data[CONF_ADDRESS]
    registry = er.async_get(hass)

    async_add_entities(
        [
            *(AtfleeScaleSensorEntity(coordinator, entry, d) for d in SCALE_SENSORS),
            AtfleeFailureCountSensor(coordinator, entry),
            AtfleeLastFailureSensor(coordinator, entry),
        ]
    )

    def has_value(subentry_id: str, description: AtfleeUserSensorDescription) -> bool:
        data = coordinator.data
        measurement = data.measurements.get(subentry_id) if data else None
        return measurement is not None and description.value_fn(measurement) is not None

    # Per user: descriptions still waiting for their first value.
    pending: dict[str, dict[str, AtfleeUserSensorDescription]] = {}
    for subentry_id, subentry in coordinator.user_subentries().items():
        entities: list[SensorEntity] = []
        pending[subentry_id] = {}
        for description in USER_SENSORS:
            if description.key in _ALWAYS_KEYS:
                entities.append(
                    AtfleeUserSensorEntity(coordinator, entry, subentry, description)
                )
                continue
            entity_id = registry.async_get_entity_id(
                "sensor", DOMAIN, user_unique_id(address, subentry_id, description.key)
            )
            reg_entry = registry.async_get(entity_id) if entity_id else None
            if reg_entry is not None:
                if (
                    has_value(subentry_id, description)
                    or _is_customised(reg_entry)
                    or _has_stored_value(hass, reg_entry.entity_id)
                ):
                    entities.append(
                        AtfleeUserSensorEntity(coordinator, entry, subentry, description)
                    )
                    continue
                # Left over from a version that created it without ever having a value.
                registry.async_remove(reg_entry.entity_id)
            pending[subentry_id][description.key] = description
        async_add_entities(entities, config_subentry_id=subentry_id)

    @callback
    def _add_ready_sensors() -> None:
        if entry.state is ConfigEntryState.UNLOAD_IN_PROGRESS:
            return
        for subentry_id, waiting in pending.items():
            ready = [d for d in waiting.values() if has_value(subentry_id, d)]
            if not ready:
                continue
            for description in ready:
                del waiting[description.key]
            subentry = entry.subentries[subentry_id]
            async_add_entities(
                [
                    AtfleeUserSensorEntity(coordinator, entry, subentry, d)
                    for d in ready
                ],
                config_subentry_id=subentry_id,
            )

    entry.async_on_unload(coordinator.async_add_listener(_add_ready_sensors))
    _add_ready_sensors()


class _AtfleeRestoreSensor(CoordinatorEntity[AtfleeDataUpdateCoordinator], RestoreSensor):
    """Sensor that falls back to its restored value while the scale sends none."""

    _attr_has_entity_name = True
    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: AtfleeDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._restored_native_value: float | int | str | None = None

    def _current_value(self) -> float | int | str | None:
        """Return the live value, or None when the scale has not sent one."""
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        """Restore previous sensor state on HA restart."""
        await super().async_added_to_hass()
        last_sensor_data = await self.async_get_last_sensor_data()
        if last_sensor_data is None:
            return
        self._restored_native_value = self._coerce_restored_value(last_sensor_data.native_value)

    def _coerce_restored_value(self, value: Any) -> float | int | str | None:
        """Convert restored state into expected value type for this entity."""
        if value is None:
            return None
        if isinstance(value, (float, int)):
            if self.entity_description.key in _INT_KEYS:
                return int(value)
            return float(value)

        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"unknown", "unavailable", "none", ""}:
                return None
            if self.entity_description.key in _INT_KEYS:
                try:
                    return int(float(value))
                except ValueError:
                    return None
            try:
                return float(value)
            except ValueError:
                return None
        return None

    @property
    def native_value(self) -> float | int | str | None:
        """Return the sensor value."""
        value = self._current_value()
        if value is not None:
            self._restored_native_value = value
            return value
        return self._restored_native_value


class AtfleeUserSensorEntity(_AtfleeRestoreSensor):
    """Measurement sensor of one user."""

    entity_description: AtfleeUserSensorDescription

    def __init__(
        self,
        coordinator: AtfleeDataUpdateCoordinator,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        description: AtfleeUserSensorDescription,
    ) -> None:
        super().__init__(coordinator, description)
        self._subentry_id = subentry.subentry_id
        self._attr_unique_id = user_unique_id(
            entry.data[CONF_ADDRESS], subentry.subentry_id, description.key
        )
        self._attr_device_info = user_device_info(entry, subentry)

    @property
    def _measurement(self) -> AtfleeMeasurement | None:
        return self.coordinator.data.measurements.get(self._subentry_id)

    def _current_value(self) -> float | int | str | None:
        measurement = self._measurement
        return None if measurement is None else self.entity_description.value_fn(measurement)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attach this user's own packet fields (not the scale-wide ones)."""
        return _measurement_attributes(self._measurement)


class AtfleeScaleSensorEntity(_AtfleeRestoreSensor):
    """Scale-level sensor (battery, diagnostics)."""

    entity_description: AtfleeScaleSensorDescription

    def __init__(
        self,
        coordinator: AtfleeDataUpdateCoordinator,
        entry: ConfigEntry,
        description: AtfleeScaleSensorDescription,
    ) -> None:
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{description.key}"
        self._attr_device_info = scale_device_info(entry)

    def _current_value(self) -> float | int | str | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attach raw packet fields; the connection sensor adds the session report."""
        state = self.coordinator.data
        attrs = _packet_attributes(state, state.latest)
        if self.entity_description.key == "connection_duration":
            # The last session's breakdown (stages, radio, likely cause); not
            # while a session runs, so it is never shown against its time.
            if not self.coordinator.session_report_pending:
                report = self.coordinator.session_reports.last
                if report:
                    attrs = {**attrs, **report}
        return attrs


def _measurement_attributes(m: AtfleeMeasurement | None) -> dict[str, Any]:
    """Fields of one measurement; the only attributes a user's sensors carry."""
    return {
        "measure_state": m.measure_state if m else None,
        "stable": m.is_stable if m else None,
        "body_composition_complete": m.is_body_composition_complete if m else None,
        "assignment": m.assignment if m else None,
        # 확장 체성분 속성
        "heart_rate": m.heart_rate if m else None,
        "support_upload_bodyfat": m.support_upload_bodyfat if m else None,
        "weight_lb": m.weight_lb if m else None,
        "weight_st": m.weight_st if m else None,
        # 패킷 구조
        "packet_command": m.packet_command if m else None,
        "packet_sequence": m.packet_sequence if m else None,
        "packet_tail": m.packet_tail if m else None,
        "extended_payload_hex": m.extended_payload_hex if m else None,
    }


def _packet_attributes(state: AtfleeState, m: AtfleeMeasurement | None) -> dict[str, Any]:
    """Scale sensors: the latest packet's fields plus the scale-wide diagnostics."""
    return {
        # 패킷 진단
        "last_packet_hex": state.last_packet_hex,
        "ble_connected": state.connected,
        "connection_started_at": (
            state.connection_started_at.isoformat() if state.connection_started_at else None
        ),
        "connection_duration_seconds": state.connection_duration_seconds,
        "measuring": state.measuring,
        **_measurement_attributes(m),
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }


class _AtfleeFailureSensor(CoordinatorEntity[AtfleeDataUpdateCoordinator], SensorEntity):
    """Diagnostic sensor backed by the coordinator's blesession SessionReports."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _key: str

    def __init__(self, coordinator: AtfleeDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        address = entry.data[CONF_ADDRESS]
        self._attr_translation_key = self._key
        self._attr_unique_id = f"{address}_{self._key}"
        self._attr_device_info = scale_device_info(entry)


class AtfleeFailureCountSensor(_AtfleeFailureSensor):
    """Number of failed sessions since the entry was loaded."""

    _key = "failure_count"
    _attr_icon = "mdi:alert-circle-outline"

    @property
    def native_value(self) -> int:
        return self.coordinator.session_reports.failures


class AtfleeLastFailureSensor(_AtfleeFailureSensor):
    """When the last failed session happened."""

    _key = "last_failure"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-alert-outline"

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.session_reports.last_failure_at

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        report = self.coordinator.session_reports.last_failure
        return dict(report) if report else None
