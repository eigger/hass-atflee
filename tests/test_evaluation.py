"""Boundary tests for the body metric evaluations (no Home Assistant)."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types

import pytest

_DIR = Path(__file__).parents[1] / "custom_components" / "atflee"
_PKG = types.ModuleType("atflee_pure_ev")
_PKG.__path__ = [str(_DIR)]
sys.modules["atflee_pure_ev"] = _PKG

ev = importlib.import_module("atflee_pure_ev.evaluation")


def _state(result):
    return None if result is None else result.state


@pytest.mark.parametrize(
    ("bmi", "state"),
    [
        (18.4, "underweight"),
        (18.5, "normal"),
        (22.9, "normal"),
        (23.0, "overweight"),
        (24.9, "overweight"),
        (25.0, "obese_1"),
        (29.9, "obese_1"),
        (30.0, "obese_2"),
        (34.9, "obese_2"),
        (35.0, "obese_3"),
    ],
)
def test_bmi_boundaries(bmi, state) -> None:
    assert _state(ev.evaluate_bmi(bmi)) == state
    assert _state(ev.evaluate_bmi(bmi, 30, True)) == state


def test_bmi_age_and_value_limits() -> None:
    assert ev.evaluate_bmi(22.0, 17) is None
    assert ev.evaluate_bmi(22.0, 100) is None
    assert _state(ev.evaluate_bmi(22.0, 18)) == "normal"
    assert _state(ev.evaluate_bmi(22.0, 99)) == "normal"
    assert ev.evaluate_bmi(0) is None
    result = ev.evaluate_bmi(22.0)
    assert (result.range_low, result.range_high) == (18.5, 23.0)


# (male, age, cuts of normal / high / very high)
_FAT_CASES = [
    (True, 30, (8, 20, 25)),
    (True, 50, (11, 22, 28)),
    (True, 70, (13, 25, 30)),
    (False, 30, (21, 33, 39)),
    (False, 50, (23, 34, 40)),
    (False, 70, (24, 36, 42)),
]


@pytest.mark.parametrize(("male", "age", "cuts"), _FAT_CASES)
def test_body_fat_boundaries(male, age, cuts) -> None:
    normal, high, very_high = cuts
    assert _state(ev.evaluate_body_fat(normal - 0.1, age, male)) == "low"
    assert _state(ev.evaluate_body_fat(normal, age, male)) == "normal"
    assert _state(ev.evaluate_body_fat(high - 0.1, age, male)) == "normal"
    assert _state(ev.evaluate_body_fat(high, age, male)) == "high"
    assert _state(ev.evaluate_body_fat(very_high - 0.1, age, male)) == "high"
    assert _state(ev.evaluate_body_fat(very_high, age, male)) == "very_high"
    result = ev.evaluate_body_fat(normal, age, male)
    assert (result.range_low, result.range_high) == (normal, high)


@pytest.mark.parametrize(
    ("age", "band_age"),
    [(18, 30), (19, 30), (39, 30), (40, 50), (59, 50), (60, 70), (80, 70), (99, 70)],
)
def test_body_fat_age_bands(age, band_age) -> None:
    for male in (True, False):
        for pct in (5.0, 15.0, 22.5, 26.0, 30.0, 35.0, 41.0, 45.0):
            assert ev.evaluate_body_fat(pct, age, male) == ev.evaluate_body_fat(
                pct, band_age, male
            )


def test_body_fat_unusable_input() -> None:
    assert ev.evaluate_body_fat(20.0, None, True) is None
    assert ev.evaluate_body_fat(20.0, 30, None) is None
    assert ev.evaluate_body_fat(20.0, 17, True) is None
    assert ev.evaluate_body_fat(20.0, 100, True) is None
    assert ev.evaluate_body_fat(0, 30, True) is None


@pytest.mark.parametrize(
    ("level", "state"),
    [
        (1, "normal"),
        (9, "normal"),
        (9.9, "normal"),
        (10, "high"),
        (14, "high"),
        (14.9, "high"),
        (15, "very_high"),
        (59, "very_high"),
    ],
)
def test_visceral_fat_boundaries(level, state) -> None:
    assert _state(ev.evaluate_visceral_fat(level)) == state


def test_visceral_fat_age_limit() -> None:
    assert ev.evaluate_visceral_fat(5, 17) is None
    assert ev.evaluate_visceral_fat(-1) is None


@pytest.mark.parametrize(
    ("male", "low", "high"), [(True, 50.0, 65.0), (False, 45.0, 60.0)]
)
def test_body_water_boundaries(male, low, high) -> None:
    assert _state(ev.evaluate_body_water(low - 0.1, 30, male)) == "low"
    assert _state(ev.evaluate_body_water(low, 30, male)) == "normal"
    assert _state(ev.evaluate_body_water(high, 30, male)) == "normal"
    assert _state(ev.evaluate_body_water(high + 0.1, 30, male)) == "high"
    assert ev.evaluate_body_water(low, None, male) is None
    assert ev.evaluate_body_water(low, 30, None) is None


def test_body_score_boundaries() -> None:
    assert _state(ev.evaluate_body_score(79)) == "unbalanced"
    assert _state(ev.evaluate_body_score(79.9)) == "unbalanced"
    assert _state(ev.evaluate_body_score(80)) == "balanced"
    assert _state(ev.evaluate_body_score(100)) == "balanced"
    assert ev.evaluate_body_score(80, 17) is None


def test_every_state_is_listed_and_documented() -> None:
    cases = [
        (ev.BMI_STATES, [ev.evaluate_bmi(v) for v in (17, 20, 24, 27, 32, 40)]),
        (ev.BODY_FAT_STATES, [ev.evaluate_body_fat(v, 30, True) for v in (5, 15, 22, 30)]),
        (ev.VISCERAL_FAT_STATES, [ev.evaluate_visceral_fat(v) for v in (5, 12, 20)]),
        (ev.BODY_WATER_STATES, [ev.evaluate_body_water(v, 30, True) for v in (40, 55, 70)]),
        (ev.BODY_SCORE_STATES, [ev.evaluate_body_score(v) for v in (50, 90)]),
    ]
    for options, results in cases:
        assert sorted(r.state for r in results) == sorted(options)
        assert all(r.standard for r in results)


def test_state_translations_match_options() -> None:
    import json

    expected = {
        "bmi_status": ev.BMI_STATES,
        "body_fat_status": ev.BODY_FAT_STATES,
        "visceral_fat_status": ev.VISCERAL_FAT_STATES,
        "body_water_status": ev.BODY_WATER_STATES,
        "body_score_status": ev.BODY_SCORE_STATES,
    }
    for path in ("strings.json", "translations/en.json", "translations/ko.json"):
        sensors = json.loads((_DIR / path).read_text(encoding="utf-8"))["entity"]["sensor"]
        for key, options in expected.items():
            assert list(sensors[key]["state"]) == options, (path, key)
