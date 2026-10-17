"""Tests for the user subentry validation helpers (no Home Assistant)."""

from __future__ import annotations

from datetime import date
import importlib
from pathlib import Path
import sys
import types

# Load the pure modules without running the integration package (it needs Home Assistant).
_DIR = Path(__file__).parents[1] / "custom_components" / "atflee"
_PKG = types.ModuleType("atflee_pure")
_PKG.__path__ = [str(_DIR)]
sys.modules["atflee_pure"] = _PKG

up = importlib.import_module("atflee_pure.user_profile")

TODAY = date(2026, 10, 17)
VALID = {
    "name": "Alice",
    "height_cm": 165,
    "birth_date": "1990-05-20",
    "sex": "female",
}


def test_valid_input_has_no_errors() -> None:
    assert up.validate_user_input(VALID, TODAY) == {}


def test_expected_weight_is_optional_but_range_checked() -> None:
    assert up.validate_user_input(VALID | {"expected_weight_kg": 62.5}, TODAY) == {}
    assert up.validate_user_input(VALID | {"expected_weight_kg": 5}, TODAY) == {
        "expected_weight_kg": "invalid_expected_weight"
    }


def test_birth_date_validation() -> None:
    assert up.validate_user_input(VALID | {"birth_date": "2026-10-18"}, TODAY) == {
        "birth_date": "birth_date_in_future"
    }
    assert up.validate_user_input(VALID | {"birth_date": "2026-10-17"}, TODAY) == {}
    assert up.validate_user_input(VALID | {"birth_date": "1899-12-31"}, TODAY) == {
        "birth_date": "birth_date_too_old"
    }
    assert up.validate_user_input(VALID | {"birth_date": "not-a-date"}, TODAY) == {
        "birth_date": "invalid_birth_date"
    }


def test_birth_date_accepts_common_text_formats() -> None:
    expected = date(1985, 3, 7)
    for text in ("1985-03-07", "1985-3-7", "1985.3.7", "1985/03/07", "19850307", " 1985-03-07 "):
        assert up.parse_birth_date(text) == expected
    for text in ("1985-02-30", "85-03-07", "", "1985-13-01", "abc"):
        assert up.parse_birth_date(text) is None


def test_height_sex_and_name_validation() -> None:
    assert "height_cm" in up.validate_user_input(VALID | {"height_cm": 79}, TODAY)
    assert "height_cm" in up.validate_user_input(VALID | {"height_cm": 251}, TODAY)
    assert "height_cm" in up.validate_user_input(VALID | {"height_cm": None}, TODAY)
    assert "sex" in up.validate_user_input(VALID | {"sex": "other"}, TODAY)
    assert up.validate_user_input(VALID | {"name": "  "}, TODAY) == {
        "name": "name_required"
    }
    assert up.validate_user_input(VALID, TODAY, existing_names=["alice"]) == {
        "name": "name_exists"
    }


def test_lowest_free_slot() -> None:
    assert up.lowest_free_slot([]) == 1
    assert up.lowest_free_slot([1, 2, 3]) == 4
    assert up.lowest_free_slot([1, 3]) == 2
    assert up.lowest_free_slot([2]) == 1


def test_normalize_user_input() -> None:
    data = up.normalize_user_input(
        VALID | {"name": " Alice ", "height_cm": 165.0, "expected_weight_kg": 60}, 2
    )
    assert data == {
        "name": "Alice",
        "height_cm": 165,
        "birth_date": "1990-05-20",
        "sex": "female",
        "slot": 2,
        "expected_weight_kg": 60.0,
    }
    assert "expected_weight_kg" not in up.normalize_user_input(VALID, 1)


def test_primary_user_is_lowest_slot() -> None:
    users = {"b": {"slot": 2}, "a": {"slot": 1}, "c": {"slot": 3}}
    assert up.primary_user_id(users) == "a"
    assert up.primary_user_id({}) is None


def test_profile_from_data() -> None:
    profile = up.profile_from_data(VALID)
    assert (profile.height_cm, profile.birth_date, profile.sex) == (
        165,
        date(1990, 5, 20),
        "female",
    )


def test_profile_from_data_rejects_unusable_data() -> None:
    assert up.profile_from_data({}) is None
    assert up.profile_from_data(VALID | {"birth_date": "garbage"}) is None
    assert up.profile_from_data(VALID | {"sex": "other"}) is None
    assert up.profile_from_data(VALID | {"height_cm": "tall"}) is None


def test_reload_needed() -> None:
    users = {"a": ("A", {"height_cm": 170})}
    live = ("enable_body_composition",)
    assert not up.reload_needed(users, dict(users), {}, {}, live)
    assert up.reload_needed(users, {}, {}, {}, live)
    assert up.reload_needed(users, {"a": ("A", {"height_cm": 171})}, {}, {}, live)
    # The live option alone never reloads, other options do.
    assert not up.reload_needed(
        users, users, {"enable_body_composition": False}, {"enable_body_composition": True}, live
    )
    assert up.reload_needed(users, users, {"notify_timeout_seconds": 12}, {"notify_timeout_seconds": 20}, live)
    assert up.reload_needed(users, users, {}, {"notify_timeout_seconds": 20}, live)


def _users() -> dict[str, dict]:
    return {
        "b": {"name": "Bob", "slot": 2},
        "a": {"name": "Alice", "slot": 1},
        "c": {"name": "Bob", "slot": 3},
    }


def test_option_labels_are_unique_and_in_slot_order() -> None:
    labels = up.user_option_labels(_users())
    assert list(labels) == ["a", "b", "c"]
    assert list(labels.values()) == ["Alice", "Bob", "Bob (2)"]
    # A user called "auto" must not shadow the auto option.
    assert up.user_option_labels({"x": {"name": "auto", "slot": 1}}) == {"x": "auto (2)"}
    assert up.user_option_labels({}) == {}


def test_resolve_order_active_default_lowest_slot() -> None:
    users = _users()
    assert up.resolve_user_id(users, "c", "b") == "c"
    assert up.resolve_user_id(users, None, "b") == "b"
    assert up.resolve_user_id(users, None, None) == "a"
    # Ids that no longer exist fall through.
    assert up.resolve_user_id(users, "gone", "b") == "b"
    assert up.resolve_user_id(users, "gone", "gone") == "a"
    assert up.resolve_user_id({}, "a", "b") is None


def test_active_selection_expires_with_injected_clock() -> None:
    now = [100.0]
    sel = up.ActiveUserSelection(timeout=600, clock=lambda: now[0])
    assert sel.user_id is None
    sel.select("a")
    now[0] += 599
    assert sel.user_id == "a"
    now[0] += 1
    assert sel.user_id is None
    # Re-selecting restarts the timeout; clear and select(None) go back to auto.
    sel.select("b")
    now[0] += 500
    sel.select("b")
    now[0] += 500
    assert sel.user_id == "b"
    sel.clear()
    assert sel.user_id is None
    sel.select(None)
    assert sel.user_id is None


def test_reload_needed_with_default_user_live() -> None:
    users = {"a": ("A", {"slot": 1})}
    live = ("enable_body_composition", "default_user")
    assert not up.reload_needed(users, users, {}, {"default_user": "a"}, live)
    assert not up.reload_needed(users, users, {"default_user": "a"}, {}, live)
    assert up.reload_needed(users, users, {}, {"default_user": "a"}, ("enable_body_composition",))
