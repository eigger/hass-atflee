"""Tests for per-user measurement merging, state building and id helpers."""

from __future__ import annotations

from datetime import datetime

import custom_components.atflee.atflee_ble.models as models
import custom_components.atflee.user_profile as up

AtfleeMeasurement = models.AtfleeMeasurement
NOW = datetime(2026, 10, 17, 12, 0, 0)


def _state(prev, measurement=None, user_id=None, **kwargs):
    return models.next_state(
        prev,
        measurement=measurement,
        user_id=user_id,
        connected=kwargs.get("connected", True),
        measuring=kwargs.get("measuring", False),
        connection_started_at=None,
        connection_duration_seconds=0,
        updated_at=NOW,
    )


# --- merge -------------------------------------------------------------------


def test_merge_fills_missing_values_from_same_user() -> None:
    prev = AtfleeMeasurement(weight_kg=70.0, bmi=22.5, heart_rate=60)
    new = AtfleeMeasurement(body_fat_pct=20.0)
    new.merge_with_previous(prev)
    assert new.weight_kg == 70.0
    assert new.bmi == 22.5
    # Fresh percentage without a weight in the packet cannot produce a mass.
    assert new.body_fat_mass is None
    # Heart rate is a per-packet reading and is not carried over.
    assert new.heart_rate is None


def test_merge_keeps_fresh_values_over_previous() -> None:
    prev = AtfleeMeasurement(weight_kg=70.0)
    new = AtfleeMeasurement(weight_kg=71.5)
    new.merge_with_previous(prev)
    assert new.weight_kg == 71.5


def test_merge_without_previous_computes_masses() -> None:
    new = AtfleeMeasurement(weight_kg=80.0, body_fat_pct=25.0)
    new.merge_with_previous(None)
    assert new.body_fat_mass == 20.0
    assert new.fat_free_mass == 60.0


def test_merge_does_not_carry_stale_mass_from_old_percentage() -> None:
    prev = AtfleeMeasurement(weight_kg=80.0, body_fat_pct=25.0, body_fat_mass=20.0)
    new = AtfleeMeasurement(weight_kg=82.0)
    new.merge_with_previous(prev)
    assert new.body_fat_pct == 25.0
    assert new.body_fat_mass == 20.0  # carried, not recomputed from the new weight


def test_merge_ignores_battery() -> None:
    prev = AtfleeMeasurement(weight_kg=70.0, battery_pct=80)
    new = AtfleeMeasurement()
    new.merge_with_previous(prev)
    assert new.battery_pct is None


# --- state building -------------------------------------------------------------


def test_state_stores_measurement_under_user() -> None:
    m = AtfleeMeasurement(weight_kg=70.0, raw_hex="aa", battery_pct=90)
    state = _state(None, m, "u1")
    assert state.measurements == {"u1": m}
    assert state.latest is m
    assert state.last_packet_hex == "aa"
    assert state.battery_pct == 90


def test_state_keeps_other_users_untouched() -> None:
    a = AtfleeMeasurement(weight_kg=60.0)
    b = AtfleeMeasurement(weight_kg=80.0)
    state = _state(_state(None, a, "u1"), b, "u2")
    assert state.measurements == {"u1": a, "u2": b}
    # Replacing one user does not alter the other, nor mutate the old state.
    prev = state
    c = AtfleeMeasurement(weight_kg=61.0)
    state = _state(prev, c, "u1")
    assert state.measurements["u1"] is c
    assert state.measurements["u2"] is b
    assert prev.measurements["u1"] is a


def test_state_without_user_only_updates_scale_level() -> None:
    first = _state(None, AtfleeMeasurement(weight_kg=70.0), "u1")
    m = AtfleeMeasurement(weight_kg=65.0, battery_pct=55, raw_hex="bb")
    state = _state(first, m, None)
    assert set(state.measurements) == {"u1"}
    assert state.measurements["u1"].weight_kg == 70.0
    assert state.latest is m
    assert state.battery_pct == 55


def test_state_keeps_battery_when_packet_has_none() -> None:
    state = _state(
        _state(None, AtfleeMeasurement(battery_pct=70), "u1"),
        AtfleeMeasurement(weight_kg=70.0),
        "u1",
    )
    assert state.battery_pct == 70


def test_state_without_measurement_carries_everything() -> None:
    m = AtfleeMeasurement(weight_kg=70.0, raw_hex="aa")
    state = _state(_state(None, m, "u1"), None, None, connected=False)
    assert state.measurements == {"u1": m}
    assert state.last_packet_hex == "aa"
    assert state.connected is False


# --- user / id helpers ------------------------------------------------------------


def test_primary_user_id_is_lowest_slot() -> None:
    users = {"b": {"slot": 2}, "a": {"slot": 3}, "c": {"slot": 1}}
    assert up.primary_user_id(users) == "c"
    assert up.primary_user_id({}) is None


def test_primary_user_id_ties_are_deterministic() -> None:
    assert up.primary_user_id({"z": {"slot": 1}, "m": {"slot": 1}}) == "m"


def test_unique_id_and_device_identifier() -> None:
    assert up.user_unique_id("AA:BB", "sub1", "weight") == "AA:BB_sub1_weight"
    assert up.user_device_identifier("AA:BB", "sub1") == "AA:BB_sub1"
    # The two users of one scale never collide.
    assert up.user_unique_id("AA:BB", "s1", "bmi") != up.user_unique_id(
        "AA:BB", "s2", "bmi"
    )
