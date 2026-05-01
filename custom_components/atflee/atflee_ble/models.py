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
