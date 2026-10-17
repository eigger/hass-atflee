"""Data models for Atflee BLE core."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


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
    subcutaneous_fat_pct: float | None = None   # 피하지방률 (subcutaneousFat)
    visceral_fat: float | None = None           # 내장지방 (visceralFat / vfal)
    muscle_pct: float | None = None             # 근육률 (muscle / musclePercent)
    muscle_mass: float | None = None            # 근육량 kg (muscleMass)
    bmr: int | None = None                      # 기초대사량 kcal (bmr)
    bone_mass: float | None = None              # 골량 kg (bone / boneMass)
    moisture_pct: float | None = None           # 수분률 (moisture / moisturePercent)
    protein_pct: float | None = None            # 단백질률 (proteinRate / protein)
    skeletal_muscle_pct: float | None = None    # 골격근률 (sm / smPercent)
    physical_age: int | None = None             # 체내나이 (bodyage / physicalAge)
    body_score: float | None = None             # 신체 점수 (bodyScore)

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

    # --- 계산된 체성분 (같은 측정의 체중 x 퍼센트로 계산해 저장) ---
    body_fat_mass: float | None = None          # 체지방량 kg
    fat_free_mass: float | None = None          # 제지방량 kg
    body_water_mass: float | None = None        # 체수분량 kg
    protein_mass: float | None = None           # 단백질량 kg
    skeletal_muscle_mass: float | None = None   # 골격근량 kg

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
        for field, pct_field in (
            ("body_water_mass", "moisture_pct"),
            ("protein_mass", "protein_pct"),
            ("skeletal_muscle_mass", "skeletal_muscle_pct"),
        ):
            if pct_field in fresh:
                setattr(self, field, mass(getattr(self, pct_field)))


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

    @property
    def impedance_channels(self) -> int:
        """Number of impedance shorts in a stable-weight message."""
        return (self.freq_count + 1) * self.impedance_count


@dataclass(slots=True)
class AtfleeState:
    """Latest coordinator state."""

    measurement: AtfleeMeasurement | None = None
    last_packet_hex: str | None = None
    user_height_cm: int | None = None
    connected: bool = False
    measuring: bool = False
    connection_started_at: datetime | None = None
    connection_duration_seconds: int = 0
    updated_at: datetime | None = None
