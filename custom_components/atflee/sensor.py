"""Sensor platform for Atflee integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, UnitOfMass, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AtfleeDataUpdateCoordinator
from .atflee_ble.models import AtfleeState


@dataclass(frozen=True, kw_only=True)
class AtfleeSensorDescription(SensorEntityDescription):
    """Atflee sensor entity description."""

    value_fn: Callable[[AtfleeState], float | int | str | None]


# ─────────────────────────────────────────────────────────────────────────────
# 기본 체중 / 체성분
# ─────────────────────────────────────────────────────────────────────────────
SENSORS: tuple[AtfleeSensorDescription, ...] = (
    AtfleeSensorDescription(
        key="weight",
        
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.measurement.weight_kg if state.measurement else None,
    ),
    AtfleeSensorDescription(
        key="body_fat",
        
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
        value_fn=lambda state: state.measurement.body_fat_pct if state.measurement else None,
    ),
    AtfleeSensorDescription(
        key="bmi",
        
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:scale-bathroom",
        value_fn=lambda state: state.measurement.bmi if state.measurement else None,
    ),
    AtfleeSensorDescription(
        key="impedance",
        
        native_unit_of_measurement="ohm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        value_fn=lambda state: state.measurement.impedance_ohm if state.measurement else None,
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # 확장 체성분
    # ─────────────────────────────────────────────────────────────────────────
    AtfleeSensorDescription(
        key="subcutaneous_fat",
        
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
        value_fn=lambda state: state.measurement.subcutaneous_fat_pct if state.measurement else None,
    ),
    AtfleeSensorDescription(
        key="visceral_fat",
        
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:stomach",
        value_fn=lambda state: state.measurement.visceral_fat if state.measurement else None,
    ),
    AtfleeSensorDescription(
        key="muscle_pct",
        
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:arm-flex",
        value_fn=lambda state: state.measurement.muscle_pct if state.measurement else None,
    ),
    AtfleeSensorDescription(
        key="muscle_mass",
        
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.measurement.muscle_mass if state.measurement else None,
    ),
    AtfleeSensorDescription(
        key="bmr",
        
        native_unit_of_measurement="kcal",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fire",
        value_fn=lambda state: state.measurement.bmr if state.measurement else None,
    ),
    AtfleeSensorDescription(
        key="bone_mass",
        
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:bone",
        value_fn=lambda state: state.measurement.bone_mass if state.measurement else None,
    ),
    AtfleeSensorDescription(
        key="moisture_pct",
        
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water",
        value_fn=lambda state: state.measurement.moisture_pct if state.measurement else None,
    ),
    AtfleeSensorDescription(
        key="protein_pct",
        
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:food-steak",
        value_fn=lambda state: state.measurement.protein_pct if state.measurement else None,
    ),
    AtfleeSensorDescription(
        key="skeletal_muscle_pct",
        
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:arm-flex-outline",
        value_fn=lambda state: state.measurement.skeletal_muscle_pct if state.measurement else None,
    ),
    AtfleeSensorDescription(
        key="physical_age",
        
        native_unit_of_measurement="years",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:calendar-heart",
        value_fn=lambda state: state.measurement.physical_age if state.measurement else None,
    ),
    AtfleeSensorDescription(
        key="body_score",
        
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:medal",
        value_fn=lambda state: state.measurement.body_score if state.measurement else None,
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # 기기 상태
    # ─────────────────────────────────────────────────────────────────────────
    AtfleeSensorDescription(
        key="battery",
        
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.measurement.battery_pct if state.measurement else None,
    ),
    AtfleeSensorDescription(
        key="heart_rate",
        
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart-pulse",
        value_fn=lambda state: state.measurement.heart_rate if state.measurement else None,
    ),
    # ─────────────────────────────────────────────────────────────────────────
    # 진단 / 디버그
    # ─────────────────────────────────────────────────────────────────────────
    AtfleeSensorDescription(
        key="verify_status",
        
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:check-circle-outline",
        value_fn=lambda state: state.measurement.verify_status if state.measurement else None,
    ),
    AtfleeSensorDescription(
        key="measure_status",
        
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:state-machine",
        value_fn=lambda state: state.measurement.measure_status if state.measurement else None,
    ),
    AtfleeSensorDescription(
        key="scale_status",
        
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:information-outline",
        value_fn=lambda state: state.measurement.scale_status if state.measurement else None,
    ),
    AtfleeSensorDescription(
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Atflee sensor entities."""
    coordinator: AtfleeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [AtfleeSensorEntity(coordinator, entry, description) for description in SENSORS]
    )


class AtfleeSensorEntity(
    CoordinatorEntity[AtfleeDataUpdateCoordinator], RestoreSensor
):
    """Base Atflee sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AtfleeDataUpdateCoordinator,
        entry: ConfigEntry,
        description: AtfleeSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_translation_key = description.key
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, address)},
            identifiers={(DOMAIN, address)},
            name=entry.title,
            manufacturer="Atflee",
            model="BLE Scale",
        )
        self._restored_native_value: float | int | str | None = None

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
        value = self.entity_description.value_fn(self.coordinator.data)
        if value is not None:
            self._restored_native_value = value
            return value
        return self._restored_native_value

    @property
    def extra_state_attributes(self) -> dict[str, str | int | bool | None]:
        """Attach raw packet and body composition fields for diagnostic purposes."""
        state = self.coordinator.data
        m = state.measurement
        return {
            # 패킷 진단
            "last_packet_hex": state.last_packet_hex,
            "user_height_cm": state.user_height_cm,
            "ble_connected": state.connected,
            "connection_started_at": (
                state.connection_started_at.isoformat() if state.connection_started_at else None
            ),
            "connection_duration_seconds": state.connection_duration_seconds,
            "measuring": state.measuring,
            "measure_state": m.measure_state if m else None,
            "stable": m.is_stable if m else None,
            "body_composition_complete": m.is_body_composition_complete if m else None,
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
            "updated_at": state.updated_at.isoformat() if state.updated_at else None,
        }
