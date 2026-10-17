"""Tests for weight-based user identification (no Home Assistant)."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types

_DIR = Path(__file__).parents[1] / "custom_components" / "atflee"
_PKG = types.ModuleType("atflee_pure")
_PKG.__path__ = [str(_DIR)]
sys.modules["atflee_pure"] = _PKG
_BLE = types.ModuleType("atflee_pure.atflee_ble")
_BLE.__path__ = [str(_DIR / "atflee_ble")]
sys.modules["atflee_pure.atflee_ble"] = _BLE

up = importlib.import_module("atflee_pure.user_profile")
models = importlib.import_module("atflee_pure.atflee_ble.models")

AtfleeMeasurement = models.AtfleeMeasurement


def _users(**expected):
    """Users a, b, c in slots 1..3; ``expected`` maps id -> expected weight."""
    users = {}
    for slot, sid in enumerate("abc", start=1):
        data = {"name": sid.upper(), "slot": slot}
        if sid in expected:
            data["expected_weight_kg"] = expected[sid]
        users[sid] = data
    return users


def _attr(weight, users, last=None, **kwargs):
    return up.attribute_weight(weight, users, last or {}, **kwargs)


def test_nearest_user_by_last_weight_is_matched() -> None:
    users = _users()
    result = _attr(81.0, users, {"a": 60.0, "b": 80.0})
    assert (result.assignment, result.user_id) == ("matched", "b")
    assert [c.user_id for c in result.candidates] == ["b", "a"]
    assert result.candidates[0].delta_kg == 1.0


def test_expected_weight_seeds_users_without_history() -> None:
    users = _users(a=60.0, b=80.0)
    assert _attr(79.0, users).user_id == "b"


def test_last_weight_wins_over_expected_weight() -> None:
    users = _users(a=60.0, b=80.0)
    # b's history says 70 now; 69 is b's, not a's expected 60.
    result = _attr(69.0, users, {"b": 70.0})
    assert (result.assignment, result.user_id) == ("matched", "b")


def test_users_without_reference_are_not_candidates() -> None:
    users = _users(a=60.0)
    result = _attr(60.5, users)
    assert result.user_id == "a"
    assert [c.user_id for c in result.candidates] == ["a"]


def test_no_history_and_no_expected_weight_falls_back_to_default() -> None:
    result = _attr(70.0, _users(), default_id="b")
    assert (result.assignment, result.user_id, result.reason) == (
        "fallback",
        "b",
        "no_candidates",
    )
    assert result.candidates == ()


def test_fallback_defaults_to_lowest_slot() -> None:
    assert _attr(70.0, _users()).user_id == "a"


def test_out_of_tolerance_falls_back_to_default() -> None:
    users = _users()
    result = _attr(
        75.0, users, {"a": 60.0, "b": 70.0}, default_id="a", fallback_max_delta_kg=20
    )
    assert (result.assignment, result.user_id, result.reason) == (
        "fallback",
        "a",
        "out_of_tolerance",
    )


def test_tolerance_boundary_is_inclusive() -> None:
    users = _users()
    assert _attr(73.0, users, {"a": 70.0, "b": 50.0}, tolerance_kg=3.0).user_id == "a"
    assert _attr(73.1, users, {"a": 70.0, "b": 50.0}, tolerance_kg=3.0).assignment != "matched"


def test_ambiguous_when_second_best_is_too_close() -> None:
    users = _users()
    result = _attr(75.0, users, {"a": 74.0, "b": 76.0}, default_id="b")
    assert (result.assignment, result.user_id, result.reason) == (
        "fallback",
        "b",
        "ambiguous",
    )


def test_margin_boundary_is_inclusive() -> None:
    users = _users()
    # deltas 0.5 and 2.0: exactly the 1.5 kg margin.
    result = _attr(75.0, users, {"a": 74.5, "b": 77.0})
    assert (result.assignment, result.user_id) == ("matched", "a")


def test_exact_tie_is_ambiguous() -> None:
    users = _users()
    result = _attr(75.0, users, {"a": 74.0, "b": 76.0})
    assert result.reason == "ambiguous"
    # Candidates are listed by slot on equal distance.
    assert [c.user_id for c in result.candidates] == ["a", "b"]


def test_single_candidate_needs_no_margin() -> None:
    users = _users(a=70.0)
    assert _attr(71.0, users).assignment == "matched"


def test_unassigned_when_far_from_default_reference() -> None:
    users = _users()
    result = _attr(
        110.0, users, {"a": 60.0, "b": 80.0}, default_id="a", fallback_max_delta_kg=15
    )
    assert (result.assignment, result.user_id, result.reason) == (
        "unassigned",
        None,
        "out_of_tolerance",
    )
    assert len(result.candidates) == 2


def test_fallback_delta_boundary_is_inclusive() -> None:
    users = _users()
    last = {"a": 60.0, "b": 100.0}
    assert _attr(75.0, users, last, default_id="a", fallback_max_delta_kg=15).user_id == "a"
    assert _attr(75.1, users, last, default_id="a", fallback_max_delta_kg=15).user_id is None


def test_default_without_reference_weight_is_never_unassigned() -> None:
    users = _users(b=80.0)
    result = _attr(150.0, users, default_id="a")
    assert (result.assignment, result.user_id) == ("fallback", "a")


def test_unassigned_without_candidates_uses_default_reference() -> None:
    users = _users()
    result = _attr(50.0, users, {"a": 80.0}, default_id="a")
    # a is a candidate here (history), 30 kg away -> unassigned.
    assert result.user_id is None and result.reason == "out_of_tolerance"


def test_stale_default_id_uses_lowest_slot_reference() -> None:
    users = _users()
    result = _attr(120.0, users, {"a": 60.0, "b": 80.0}, default_id="gone")
    assert result.assignment == "unassigned"


def test_single_user_is_always_that_user() -> None:
    users = {"a": {"name": "A", "slot": 1, "expected_weight_kg": 60.0}}
    for weight in (10.0, 60.0, 250.0):
        result = _attr(weight, users, {"a": 60.0})
        assert (result.assignment, result.user_id) == ("default", "a")


def test_selected_user_always_wins() -> None:
    users = _users()
    result = _attr(100.0, users, {"a": 60.0, "b": 100.0}, active_id="a")
    assert (result.assignment, result.user_id) == ("selected", "a")


def test_stale_selection_is_ignored() -> None:
    users = _users()
    result = _attr(60.5, users, {"a": 60.0, "b": 90.0}, active_id="gone")
    assert (result.assignment, result.user_id) == ("matched", "a")


def test_no_users_is_unassigned() -> None:
    result = _attr(70.0, {})
    assert (result.assignment, result.user_id, result.reason) == (
        "unassigned",
        None,
        "no_users",
    )


def test_reference_weight_ignores_invalid_values() -> None:
    assert up.reference_weight({"expected_weight_kg": 65}, None) == 65.0
    assert up.reference_weight({"expected_weight_kg": 65}, 70.5) == 70.5
    assert up.reference_weight({}, "junk") is None
    assert up.reference_weight({"expected_weight_kg": 0}, 0) is None


def test_sanitize_last_weights_drops_removed_users_and_junk() -> None:
    raw = {"a": 70.2, "gone": 80.0, "b": "x", "c": -3, "d": 55}
    assert up.sanitize_last_weights(raw, ["a", "b", "c"]) == {"a": 70.2}
    assert up.sanitize_last_weights(None, ["a"]) == {}
    assert up.sanitize_last_weights([1, 2], ["a"]) == {}


# --- B1 profile mismatch ------------------------------------------------------


def test_drop_scale_composition_clears_scale_values_only() -> None:
    m = AtfleeMeasurement(
        weight_kg=72.0,
        bmi=22.0,
        body_fat_pct=18.0,
        muscle_pct=40.0,
        body_score=80.0,
        impedance_ohm=500,
        impedances_ohm=(500.0,) * 10,
        heart_rate=70,
        is_stable=True,
        is_body_composition_complete=True,
        assignment="matched",
    )
    m.drop_scale_composition()
    assert m.bmi is None and m.body_fat_pct is None
    assert m.muscle_pct is None and m.body_score is None
    # Raw readings and flags stay so the host can compute from them.
    assert m.weight_kg == 72.0
    assert m.impedances_ohm == (500.0,) * 10
    assert m.impedance_ohm == 500
    assert m.heart_rate == 70
    assert m.is_body_composition_complete is True


def test_dropped_body_fat_does_not_produce_a_mass() -> None:
    m = AtfleeMeasurement(weight_kg=72.0, body_fat_pct=18.0)
    m.drop_scale_composition()
    m.merge_with_previous(None)
    assert m.body_fat_pct is None and m.body_fat_mass is None


def test_assignment_is_not_carried_between_measurements() -> None:
    prev = AtfleeMeasurement(weight_kg=70.0, assignment="matched")
    new = AtfleeMeasurement(weight_kg=71.0)
    new.merge_with_previous(prev)
    assert new.assignment is None


# --- session decision timing ---------------------------------------------------


def _observe(att, weight, stable, users, last=None):
    return att.observe(weight, stable, users, last or {}, default_id="a")


def test_unstable_ramp_does_not_decide_the_session() -> None:
    users = _users()
    last = {"a": 60.0, "b": 80.0}
    att = up.SessionAttributor()
    # A2 ramp: 35 kg would have been unassigned (or a wrong match) if it decided.
    for weight in (35.0, 52.0, 71.0):
        assert _observe(att, weight, False, users, last) is None
        assert att.attribution is None
    decided = _observe(att, 80.0, True, users, last)
    assert (decided.assignment, decided.user_id) == ("matched", "b")


def test_session_is_decided_once() -> None:
    users = _users()
    last = {"a": 60.0, "b": 80.0}
    att = up.SessionAttributor()
    assert _observe(att, 80.0, True, users, last).user_id == "b"
    assert _observe(att, 60.0, True, users, last) is None
    assert att.attribution.user_id == "b"
    att.reset()
    assert _observe(att, 60.0, True, users, last).user_id == "a"


def test_no_decision_without_weight_or_users() -> None:
    att = up.SessionAttributor()
    assert _observe(att, None, True, _users()) is None
    assert _observe(att, 0, True, _users()) is None
    assert _observe(att, 70.0, True, {}) is None
    assert att.attribution is None


def test_stable_unassigned_weight_decides_unassigned() -> None:
    att = up.SessionAttributor()
    result = _observe(att, 120.0, True, _users(), {"a": 60.0, "b": 80.0})
    assert result.assignment == "unassigned"


# --- storing weights -----------------------------------------------------------


def test_should_store_weight_by_assignment() -> None:
    user = {"expected_weight_kg": 60.0}
    for assignment in ("matched", "selected", "default"):
        assert up.should_store_weight(assignment, user, 61.0)
    assert not up.should_store_weight(None, user, None)
    assert not up.should_store_weight("unassigned", user, None)


def test_fallback_only_seeds_a_user_without_reference() -> None:
    assert up.should_store_weight("fallback", {}, None)
    assert not up.should_store_weight("fallback", {}, 60.0)
    assert not up.should_store_weight("fallback", {"expected_weight_kg": 60.0}, None)


def test_guest_fallback_does_not_shift_the_default_users_reference() -> None:
    users = _users()
    last = {"a": 60.0, "b": 75.0}

    def weigh(weight):
        result = _attr(weight, users, last, default_id="a")
        if up.should_store_weight(result.assignment, users[result.user_id], last.get(result.user_id)):
            last[result.user_id] = weight
        return result

    guest = weigh(68.5)  # between both, outside the margin -> fallback to a
    assert (guest.assignment, guest.user_id) == ("fallback", "a")
    assert last["a"] == 60.0
    b = weigh(73.0)
    assert (b.assignment, b.user_id) == ("matched", "b")
    assert last == {"a": 60.0, "b": 73.0}
