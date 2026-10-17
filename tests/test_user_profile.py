"""Tests for the user subentry validation and v1 -> v2 migration helpers (no Home Assistant)."""

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
    users = [{"name": "B", "slot": 2}, {"name": "A", "slot": 1}, {"name": "C", "slot": 3}]
    assert up.primary_user_data(users)["name"] == "A"
    assert up.primary_user_data([]) is None


def test_profile_from_data_defaults() -> None:
    profile = up.profile_from_data({})
    assert (profile.height_cm, profile.birth_date, profile.sex) == (
        170,
        date(1990, 1, 1),
        "male",
    )
    profile = up.profile_from_data(VALID)
    assert (profile.height_cm, profile.birth_date, profile.sex) == (
        165,
        date(1990, 5, 20),
        "female",
    )
    assert up.profile_from_data({"birth_date": "garbage"}).birth_date == date(1990, 1, 1)


def test_migration_moves_profile_into_user() -> None:
    result = up.migrate_v1_to_v2(
        {
            "address": "AA:BB",
            "height_cm": 180,
            "birth_year": 1985,
            "sex": "female",
            "notify_timeout_seconds": 12,
        },
        {"height_cm": 175, "enable_body_composition": True},
    )
    assert result.user_data == {
        "name": "User 1",
        "height_cm": 175,  # options win over data
        "birth_date": "1985-01-01",
        "sex": "female",
        "slot": 1,
    }
    assert result.user_title == "User 1"
    assert result.entry_data == {"address": "AA:BB", "notify_timeout_seconds": 12}
    assert result.entry_options == {"enable_body_composition": True}


def test_migration_uses_defaults_for_missing_or_bad_values() -> None:
    result = up.migrate_v1_to_v2(
        {"address": "AA:BB"}, {"birth_year": "x", "sex": "robot", "height_cm": 9999}
    )
    assert result.user_data == {
        "name": "User 1",
        "height_cm": 250,
        "birth_date": "1990-01-01",
        "sex": "male",
        "slot": 1,
    }
    assert result.entry_data == {"address": "AA:BB"}
    assert result.entry_options == {}


def test_migration_is_idempotent_on_migrated_data() -> None:
    first = up.migrate_v1_to_v2({"address": "AA:BB", "height_cm": 160}, {})
    again = up.migrate_v1_to_v2(first.entry_data, first.entry_options)
    assert again.entry_data == first.entry_data
    assert again.entry_options == first.entry_options


def test_legacy_entity_unique_ids() -> None:
    assert up.legacy_entity_unique_ids("AA:BB") == (
        ("number", "AA:BB_height_cm"),
        ("number", "AA:BB_birth_year"),
        ("select", "AA:BB_sex"),
    )
