"""Data models for Atflee BLE core."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


# Percentages whose arrival in a packet triggers a fresh kg computation.
_FRESH_PCT_FIELDS = (
    "body_fat_pct",
    "moisture_pct",
    "protein_pct",
    "skeletal_muscle_pct",
)

# Fields carried over from the user's previous measurement when a packet omits them.
_CARRIED_FIELDS = (
    "weight_kg",
    "weight_lb",
    "weight_st",
    "bmi",
    "body_fat_pct",
    "impedance_ohm",
    "subcutaneous_fat_pct",
    "visceral_fat",
    "muscle_pct",
    "muscle_mass",
    "bmr",
    "bone_mass",
    "moisture_pct",
    "protein_pct",
    "skeletal_muscle_pct",
    "physical_age",
    "body_score",
    "body_fat_mass",
    "fat_free_mass",
    "body_water_mass",
    "protein_mass",
    "skeletal_muscle_mass",
)


# Values the scale computes itself (from the profile it was given); they are
# not valid for a user other than the one the profile was sent for.
_SCALE_COMPOSITION_FIELDS = (
    "bmi",
    "body_fat_pct",
    "subcutaneous_fat_pct",
    "visceral_fat",
    "muscle_pct",
    "muscle_mass",
    "bmr",
    "bone_mass",
    "moisture_pct",
    "protein_pct",
    "skeletal_muscle_pct",
    "physical_age",
    "body_score",
)


@dataclass(slots=True)
class AtfleeMeasurement:
    """Single body measurement payload."""

    # --- 기본 체중 ---
    weight_kg: float | None = None
    weight_lb: float | None = None
    weight_st: float | None = None

    # --- 기본 체성분 ---
    body_fat_pct: float | None = None
    bmi: float | None = None
    impedance_ohm: int | None = None
    impedances_ohm: tuple[float, ...] | None = None  # every channel in packet order

    # --- 확장 체성분 ---
    subcutaneous_fat_pct: float | None = None  # 피하지방률 (subcutaneousFat)
    visceral_fat: float | None = None  # 내장지방 (visceralFat / vfal)
    muscle_pct: float | None = None  # 근육률 (muscle / musclePercent)
    muscle_mass: float | None = None  # 근육량 kg (muscleMass)
    bmr: int | None = None  # 기초대사량 kcal (bmr)
    bone_mass: float | None = None  # 골량 kg (bone / boneMass)
    moisture_pct: float | None = None  # 수분률 (moisture / moisturePercent)
    protein_pct: float | None = None  # 단백질률 (proteinRate / protein)
    skeletal_muscle_pct: float | None = None  # 골격근률 (sm / smPercent)
    physical_age: int | None = None  # 체내나이 (bodyage / physicalAge)
    body_score: float | None = None  # 신체 점수 (bodyScore)

    # --- 기기 상태 ---
    battery_pct: int | None = None
    heart_rate: int | None = None
    user_id: int | None = None  # scale-side user id carried by A7 results
    verify_status: int | None = None
    measure_status: int | None = None
    scale_status: int | None = None
    support_upload_bodyfat: bool | None = None

    # --- 패킷 진단 ---
    packet_command: int | None = None
    packet_sequence: int | None = None
    packet_tail: int | None = None
    extended_payload_hex: str | None = None
    measure_state: str | None = None
    is_stable: bool | None = None
    is_body_composition_complete: bool = False
    raw_hex: str | None = None
    # How the measurement was attributed to its user (set by the coordinator).
    assignment: str | None = None

    # --- 계산된 체성분 (같은 측정의 체중 x 퍼센트로 계산해 저장) ---
    body_fat_mass: float | None = None  # 체지방량 kg
    fat_free_mass: float | None = None  # 제지방량 kg
    body_water_mass: float | None = None  # 체수분량 kg
    protein_mass: float | None = None  # 단백질량 kg
    skeletal_muscle_mass: float | None = None  # 골격근량 kg

    def compute_masses(self, fresh: frozenset[str], weight: float | None) -> None:
        """Compute kg values from percentages that arrived with this packet.

        ``fresh`` names the percentage fields set by the current packet and
        ``weight`` is the weight carried by that same packet, so a mass is never
        built from a percentage or weight of an earlier measurement. A fresh
        percentage that cannot produce a valid mass clears the stale value.
        """

        def mass(pct: float | None) -> float | None:
            if weight is None or pct is None or not 0.0 <= pct <= 100.0:
                return None
            return round(weight * pct / 100.0, 2)

        if "body_fat_pct" in fresh:
            fat = mass(self.body_fat_pct)
            self.body_fat_mass = fat
            self.fat_free_mass = None if fat is None else round(weight - fat, 2)
        for mass_field, pct_field in (
            ("body_water_mass", "moisture_pct"),
            ("protein_mass", "protein_pct"),
            ("skeletal_muscle_mass", "skeletal_muscle_pct"),
        ):
            if pct_field in fresh:
                setattr(self, mass_field, mass(getattr(self, pct_field)))

    def drop_scale_composition(self) -> None:
        """Forget composition values the scale computed for another profile."""
        for name in _SCALE_COMPOSITION_FIELDS:
            setattr(self, name, None)

    def merge_with_previous(self, prev: AtfleeMeasurement | None) -> None:
        """Keep the last known values when this packet omits them.

        ``prev`` must be the previous measurement of the *same user*; values are
        never carried over between users. Scale-level fields (battery, status
        codes) are not merged here, they live on :class:`AtfleeState`.
        """
        fresh = frozenset(
            name for name in _FRESH_PCT_FIELDS if getattr(self, name) is not None
        )
        packet_weight = self.weight_kg
        if prev is not None:
            for name in _CARRIED_FIELDS:
                if getattr(self, name) is None:
                    setattr(self, name, getattr(prev, name))
        self.compute_masses(fresh, packet_weight)


@dataclass(slots=True)
class AtfleeDeviceInfo:
    """Capabilities reported by the scale in its device-info (A1) message."""

    kg_division: int = 0
    support_hr: bool = False
    support_gravity: bool = False
    support_balance: bool = False
    eight_electrode: bool = False
    freq_count: int = 0
    impedance_scaled: bool = False  # impedance shorts carry ohm * 10
    impedance_count: int = 1
    function_flags: int = 0  # bit0 impedance, bit1 balance, bit2 hr, bit3 gravity
    algorithm_type: int = 0
    protocol_ver: int = 0
    raw_hex: str = ""  # message body as received, for diagnostics

    @property
    def impedance_channels(self) -> int:
        """Number of impedance shorts in a stable-weight message."""
        return (self.freq_count + 1) * self.impedance_count

    @property
    def electrode_count(self) -> int:
        """Electrodes the scale measures with (8 or 4)."""
        return 8 if self.eight_electrode else 4

    @property
    def frequency_count(self) -> int:
        """Impedance measuring frequencies."""
        return self.freq_count + 1


@dataclass(frozen=True, slots=True)
class AtfleeHardwareInfo:
    """Strings read from the standard BLE Device Information service (0x180A)."""

    manufacturer: str | None = None  # 2A29
    model: str | None = None  # 2A24
    serial_number: str | None = None  # 2A25
    hardware_revision: str | None = None  # 2A27
    firmware_revision: str | None = None  # 2A26
    software_revision: str | None = None  # 2A28

    def as_dict(self) -> dict[str, str]:
        """Non-empty fields, for storage and diagnostics."""
        return {
            name: value
            for name in self.__slots__
            if (value := getattr(self, name)) is not None
        }

    @classmethod
    def from_dict(cls, data: object) -> AtfleeHardwareInfo | None:
        """Rebuild from ``as_dict`` output; None when nothing usable is stored."""
        if not isinstance(data, dict):
            return None
        values = {
            name: value
            for name in cls.__slots__
            if isinstance(value := data.get(name), str) and value
        }
        return cls(**values) if values else None

    def registry_fields(self) -> dict[str, str]:
        """Device registry fields this info fills in (only the known ones).

        The manufacturer string is deliberately not used: the device page keeps
        the "Atflee" brand.
        """
        fields = {
            "model": self.model,
            "serial_number": self.serial_number,
            "hw_version": self.hardware_revision,
            "sw_version": self.firmware_revision or self.software_revision,
        }
        return {key: value for key, value in fields.items() if value}


@dataclass(slots=True)
class AtfleeState:
    """Latest coordinator state.

    Measurements are kept per user (keyed by the user subentry id). ``latest``
    is the most recent packet regardless of who it was attributed to; it feeds
    the scale-level diagnostics and the raw packet attributes.
    """

    measurements: dict[str, AtfleeMeasurement] = field(default_factory=dict)
    latest: AtfleeMeasurement | None = None
    battery_pct: int | None = None
    last_packet_hex: str | None = None
    connected: bool = False
    measuring: bool = False
    connection_started_at: datetime | None = None
    connection_duration_seconds: int = 0
    updated_at: datetime | None = None


def next_state(
    prev: AtfleeState | None,
    *,
    measurement: AtfleeMeasurement | None,
    user_id: str | None,
    connected: bool,
    measuring: bool,
    connection_started_at: datetime | None,
    connection_duration_seconds: int,
    updated_at: datetime,
) -> AtfleeState:
    """Build the next state from the previous one and an optional new packet.

    A packet attributed to a user replaces only that user's entry; the other
    users' measurements are carried over untouched. A packet without a user
    (``user_id`` is None) only updates the scale-level fields.
    """
    measurements = dict(prev.measurements) if prev else {}
    latest = prev.latest if prev else None
    battery_pct = prev.battery_pct if prev else None
    last_packet_hex = prev.last_packet_hex if prev else None
    if measurement is not None:
        latest = measurement
        last_packet_hex = measurement.raw_hex
        if measurement.battery_pct is not None:
            battery_pct = measurement.battery_pct
        if user_id is not None:
            measurements[user_id] = measurement
    return AtfleeState(
        measurements=measurements,
        latest=latest,
        battery_pct=battery_pct,
        last_packet_hex=last_packet_hex,
        connected=connected,
        measuring=measuring,
        connection_started_at=connection_started_at,
        connection_duration_seconds=connection_duration_seconds,
        updated_at=updated_at,
    )
