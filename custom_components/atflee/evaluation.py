"""Plain-language evaluations of body metrics (no Home Assistant).

Each classifier maps a measured value to one of a few English state slugs using
a published reference range. They are estimates for information only, not
medical advice. Ranges are half-open: ``low`` is part of the band and ``high``
is the first value of the next one (except body water, whose upper limit is
inclusive).
"""

from __future__ import annotations

from dataclasses import dataclass

# Same adult range the body composition calculation supports.
MIN_AGE = 18
MAX_AGE = 99

DISCLAIMER = "Estimate for information only, not medical advice."

# Source and version of each reference range, shown as the ``standard`` attribute.
STANDARD_BMI = "KSSO 2022 (Haam et al., J Obes Metab Syndr 2023), Asia-Pacific BMI classes"
STANDARD_BODY_FAT = "Gallagher et al., Am J Clin Nutr 2000;72:694, age-banded"
STANDARD_VISCERAL_FAT = "Omron/InBody level convention (1-9 normal, 10-14 high, 15+ very high)"
STANDARD_BODY_WATER = "Tanita EU total body water ranges (low confidence)"
STANDARD_BODY_SCORE = "InBody score convention (80 and above is balanced)"

# BMI classes: (upper bound exclusive, state).
BMI_BANDS: tuple[tuple[float, str], ...] = (
    (18.5, "underweight"),
    (23.0, "normal"),
    (25.0, "overweight"),
    (30.0, "obese_1"),
    (35.0, "obese_2"),
)
BMI_TOP = "obese_3"
BMI_NORMAL = (18.5, 23.0)

# Body fat %: per sex and age band (20-39, 40-59, 60+), the lower bounds of
# normal, high and very high. Ages 18-19 use the first band, 80+ the last.
BODY_FAT_CUTS: dict[bool, tuple[tuple[float, float, float], ...]] = {
    True: ((8.0, 20.0, 25.0), (11.0, 22.0, 28.0), (13.0, 25.0, 30.0)),
    False: ((21.0, 33.0, 39.0), (23.0, 34.0, 40.0), (24.0, 36.0, 42.0)),
}

# Visceral fat level: lower bounds of high and very high.
VISCERAL_HIGH = 10.0
VISCERAL_VERY_HIGH = 15.0

# Body water %: normal range (inclusive) per sex.
BODY_WATER_RANGE: dict[bool, tuple[float, float]] = {
    True: (50.0, 65.0),
    False: (45.0, 60.0),
}

BODY_SCORE_BALANCED = 80.0

BMI_STATES = ["underweight", "normal", "overweight", "obese_1", "obese_2", "obese_3"]
BODY_FAT_STATES = ["low", "normal", "high", "very_high"]
VISCERAL_FAT_STATES = ["normal", "high", "very_high"]
BODY_WATER_STATES = ["low", "normal", "high"]
BODY_SCORE_STATES = ["balanced", "unbalanced"]


@dataclass(frozen=True)
class Evaluation:
    """A classified value and the reference range it was judged against."""

    state: str
    standard: str
    range_low: float | None = None
    range_high: float | None = None


def _adult(age: int | None) -> bool:
    return age is not None and MIN_AGE <= age <= MAX_AGE


def evaluate_bmi(bmi: float, age: int | None = None, male: bool | None = None) -> Evaluation | None:
    """Classify BMI; a known age outside the adult range gives no result."""
    if bmi <= 0 or (age is not None and not _adult(age)):
        return None
    state = next((s for limit, s in BMI_BANDS if bmi < limit), BMI_TOP)
    return Evaluation(state, STANDARD_BMI, *BMI_NORMAL)


def evaluate_body_fat(pct: float, age: int | None, male: bool | None) -> Evaluation | None:
    """Classify body fat % against the age and sex band."""
    if pct <= 0 or male is None or not _adult(age):
        return None
    band = 0 if age < 40 else 1 if age < 60 else 2
    normal, high, very_high = BODY_FAT_CUTS[male][band]
    if pct < normal:
        state = "low"
    elif pct < high:
        state = "normal"
    elif pct < very_high:
        state = "high"
    else:
        state = "very_high"
    return Evaluation(state, STANDARD_BODY_FAT, normal, high)


def evaluate_visceral_fat(
    level: float, age: int | None = None, male: bool | None = None
) -> Evaluation | None:
    """Classify the visceral fat level (adults only when the age is known)."""
    if level < 0 or (age is not None and not _adult(age)):
        return None
    if level < VISCERAL_HIGH:
        state = "normal"
    elif level < VISCERAL_VERY_HIGH:
        state = "high"
    else:
        state = "very_high"
    return Evaluation(state, STANDARD_VISCERAL_FAT, 1.0, VISCERAL_HIGH)


def evaluate_body_water(pct: float, age: int | None, male: bool | None) -> Evaluation | None:
    """Classify body water % against the sex range."""
    if pct <= 0 or male is None or not _adult(age):
        return None
    low, high = BODY_WATER_RANGE[male]
    state = "low" if pct < low else "high" if pct > high else "normal"
    return Evaluation(state, STANDARD_BODY_WATER, low, high)


def evaluate_body_score(
    score: float, age: int | None = None, male: bool | None = None
) -> Evaluation | None:
    """Classify the body score as balanced or not."""
    if score < 0 or (age is not None and not _adult(age)):
        return None
    state = "balanced" if score >= BODY_SCORE_BALANCED else "unbalanced"
    return Evaluation(state, STANDARD_BODY_SCORE, BODY_SCORE_BALANCED, None)
