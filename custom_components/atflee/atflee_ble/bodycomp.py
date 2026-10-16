"""Body composition for 8-electrode Atflee scales.

The scale only reports weight and ten impedance channels (five electrode
paths at two frequencies); the composition values are computed on the
receiving side. This module is a port of that calculation for adults
(age 18+), using single-precision rounding where the original does.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import struct

# Weight/height/age limits outside which the calculation yields nothing.
_HEIGHT_RANGE = (100, 220)
_ADULT_AGE = 18  # the child BMI table is not ported
_MAX_AGE = 99
_WEIGHT_RANGE = (20.0, 200.0)
MIN_IMPEDANCE_OHM = 10.0
IMPEDANCE_CHANNELS = 10


@dataclass(frozen=True, slots=True)
class BodyComposition:
    """Result of the composition calculation."""

    bmi: float
    body_fat_pct: float
    muscle_pct: float
    muscle_mass_kg: float
    subcutaneous_fat_pct: float
    visceral_fat: float
    bone_mass_kg: float
    mineral_mass_kg: float
    water_pct: float
    protein_pct: float
    skeletal_muscle_pct: float
    bmr_kcal: int
    physical_age: int
    whr: float
    body_score: int
    weight_target_kg: float
    body_fat_mass_control_kg: float
    muscle_mass_control_kg: float


def _f32(value: float) -> float:
    return struct.unpack("f", struct.pack("f", value))[0]


def _round1(value: float) -> float:
    """One-decimal rounding the way the original does it (float32 digits)."""
    as_float = _f32(value)
    digits = _f32(math.fmod(as_float, 1.0) * 10.0)
    if _f32(math.fmod(digits, 1.0)) > 0.5:
        digits = _f32(digits + 1.0)
    return _f32(_f32(float(int(digits)) / 10.0) + _f32(float(int(value))))


def _standard_bmi(male: bool) -> float:
    return 22.0 if male else 21.0


def _standard_weight(height_cm: int, male: bool) -> float:
    meters = _f32(_f32(height_cm) / 100.0)
    return _f32(_f32(meters * meters) * _f32(_standard_bmi(male)))


def _standard_bfm(height_cm: int, male: bool) -> float:
    return _f32((0.15 if male else 0.23) * _standard_weight(height_cm, male))


def _standard_ffm(height_cm: int, male: bool) -> float:
    return _f32((0.85 if male else 0.77) * _standard_weight(height_cm, male))


def _score(height_cm: int, weight: float, male: bool, body_fat: float) -> int:
    weight32 = _f32(weight)
    fat_mass = _f32(_f32(_f32(body_fat) / 100.0) * weight32)
    standard = _standard_weight(height_cm, male)
    fat_excess = _f32(fat_mass - _f32((0.15 if male else 0.23) * standard))
    lean = _f32(_f32(weight32 - fat_mass) - _f32((0.85 if male else 0.77) * standard))
    slope = -0.958 if fat_excess >= 0.0 else 0.983
    return int(float(lean) + 80.0 + slope * float(fat_excess))


def _physical_age_offset(body_fat: float, male: bool) -> int:
    if male:
        for limit, offset in ((14.0, -3), (19.0, -2), (24.0, -1), (27.0, 1)):
            if body_fat < limit:
                return offset
        for limit, offset in ((30.0, 2), (33.0, 3), (36.0, 4)):
            if body_fat < limit:
                return offset
        return 5
    for limit, offset in ((24.0, -3), (28.0, -2), (32.0, -1), (35.0, 1)):
        if body_fat < limit:
            return offset
    for limit, offset in ((38.0, 2), (42.0, 3), (45.0, 4)):
        if body_fat < limit:
            return offset
    return 0 if body_fat < 46.0 else 5


def calculate_body_composition(
    weight_kg: float,
    height_cm: int,
    age: int,
    male: bool,
    impedances: tuple[float, ...] | list[float],
) -> BodyComposition | None:
    """Return the composition, or None when the inputs are unusable."""
    if len(impedances) < IMPEDANCE_CHANNELS:
        return None
    imp = [float(value) for value in impedances[:IMPEDANCE_CHANNELS]]
    if any(value < MIN_IMPEDANCE_OHM for value in imp):
        return None
    if not _HEIGHT_RANGE[0] <= height_cm <= _HEIGHT_RANGE[1]:
        return None
    if not _ADULT_AGE <= age <= _MAX_AGE:
        return None
    if not _WEIGHT_RANGE[0] <= weight_kg <= _WEIGHT_RANGE[1]:
        return None

    w = float(weight_kg)
    h = float(height_cm)
    ratio = w / h
    bmi = _f32(_round1(w * 10000.0 / (height_cm * height_cm)))
    i0, i1, i2, i3, i4, i5, i6, i7, i8, i9 = imp
    female = 0.0 if male else 1.0

    body_fat = (
        i9 * 0.000613
        + i8 * 0.001855
        + i7 * 0.001753
        + i6 * 0.00053
        + i5 * 0.003617
        + h * 0.003941
        + w * -0.023621
        + ratio * 5.4296
        + i0 * -3.4e-05
        + i1 * -0.000388
        + i2 * -0.001114
        + i3 * -0.001663
        + i4 * -3.2e-05
        - 1.414658
    ) * 100.0
    if body_fat >= 3.0:
        body_fat = min(body_fat, 60.0)
    else:
        body_fat += 0.1  # the original adds a small random amount here

    if body_fat <= 0.0:
        return None
    fat_mass = w * body_fat / 100.0
    lean = w - fat_mass
    subcutaneous = body_fat * (body_fat * -0.0002 + 0.72)
    age_now = age + _physical_age_offset(body_fat, male)

    water_mass = lean * 0.732621 + 0.036342
    protein_mass = lean * 0.203185 - 0.26218
    sex_term = h * -0.015717 + female * -0.163382
    mineral_mass = (lean - water_mass) - protein_mass
    muscle_mass = lean - mineral_mass
    skeletal_mass = sex_term + muscle_mass * 0.660723 - 0.201168
    whr = (
        h * 0.002569
        + w * 0.007588
        + skeletal_mass * 0.04475
        + lean * -0.03668
        + female * -0.0299
        + 0.510985
    )
    visceral = float(
        int(w * 0.452039 + skeletal_mass * -0.774808 + whr * 5.423244 - 6.496948)
    )
    visceral = max(visceral, 1.0)

    bone = (
        i8 * 0.00467
        + w * 0.09951
        + h * -0.00933
        + ratio * -15.775247
        + i0 * -0.00521
        + i1 * 0.001242
        + i2 * 0.005222
        + i3 * -0.004827
        + i4 * 0.004467
        + i5 * -0.003649
        + i6 * -0.00212
        + i7 * -0.005797
        + i9 * -0.005705
        + 4.278624
    ) * 10.0

    standard_fat = _round1(_standard_bfm(height_cm, male))
    standard_lean = max(_round1(_standard_ffm(height_cm, male)), 0.0)
    fat_control = _f32(_round1(standard_fat - fat_mass))
    muscle_control = max(_round1(standard_lean - lean), 0.0)

    return BodyComposition(
        bmi=round(bmi, 1),
        body_fat_pct=_round1(body_fat),
        muscle_pct=_round1(muscle_mass / w * 100.0),
        muscle_mass_kg=round(muscle_mass, 2),
        subcutaneous_fat_pct=_round1(subcutaneous),
        visceral_fat=visceral,
        bone_mass_kg=round(_round1(bone) / 10.0, 2),
        mineral_mass_kg=round(_round1(mineral_mass * 10.0) / 10.0, 2),
        water_pct=_round1(water_mass / w * 100.0),
        protein_pct=_round1(protein_mass / w * 100.0),
        skeletal_muscle_pct=_round1(skeletal_mass / w * 100.0),
        bmr_kcal=int(lean * 21.6 + 370.0),
        physical_age=age_now,
        whr=round(whr, 3),
        body_score=_score(height_cm, w, male, body_fat),
        weight_target_kg=_round1(w + muscle_control + fat_control),
        body_fat_mass_control_kg=_round1(fat_control),
        muscle_mass_control_kg=_round1(muscle_control),
    )
