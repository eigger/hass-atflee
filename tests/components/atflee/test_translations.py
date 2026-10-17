"""Translation parity and form-error coverage."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import custom_components.atflee.user_profile as up
import custom_components.atflee.const as const

_DIR = Path(__file__).parents[3] / "custom_components" / "atflee"

FILES = {
    "strings": _DIR / "strings.json",
    "en": _DIR / "translations" / "en.json",
    "ko": _DIR / "translations" / "ko.json",
}


def _load(name: str) -> dict:
    return json.loads(FILES[name].read_text(encoding="utf-8"))


def _flatten(data: dict, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys |= _flatten(value, path)
        else:
            keys.add(path)
    return keys


def test_translation_keys_match() -> None:
    reference = _flatten(_load("strings"))
    for name in ("en", "ko"):
        keys = _flatten(_load(name))
        assert keys == reference, (name, sorted(keys ^ reference))


def test_validation_errors_are_translated() -> None:
    # Every error key validate_user_input can produce, found by feeding it
    # one invalid field at a time.
    valid = {
        "name": "Alice",
        "height_cm": 165,
        "birth_date": "1990-05-20",
        "sex": "female",
    }
    today = date(2026, 10, 17)
    bad_inputs = [
        {**valid, "name": ""},
        {**valid, "height_cm": 10},
        {**valid, "birth_date": "nope"},
        {**valid, "birth_date": "2030-01-01"},
        {**valid, "birth_date": "1700-01-01"},
        {**valid, "sex": "x"},
        {**valid, "expected_weight_kg": 1},
    ]
    produced = {
        error
        for data in bad_inputs
        for error in up.validate_user_input(data, today).values()
    }
    produced |= set(
        up.validate_user_input(valid, today, existing_names={"alice"}).values()
    )
    assert {"name_required", "invalid_height", "invalid_birth_date"} <= produced
    for name in FILES:
        data = _load(name)
        for section in (
            data["config"]["error"],
            data["config_subentries"]["user"]["error"],
        ):
            assert produced <= set(section), (name, produced - set(section))


def test_options_form_keys_are_translated() -> None:
    expected = {
        const.CONF_NOTIFY_TIMEOUT_SECONDS,
        const.CONF_ENABLE_BODY_COMP,
        const.CONF_DEFAULT_USER,
        const.CONF_MATCH_TOLERANCE_KG,
        const.CONF_FALLBACK_MAX_DELTA_KG,
    }
    for name in FILES:
        init = _load(name)["options"]["step"]["init"]
        assert set(init["data"]) == expected
        assert set(init["data_description"]) <= expected


def test_profile_sensor_translations_and_helper():
    for name in FILES:
        sensors = _load(name)["entity"]["sensor"]
        for key in ("profile_height", "profile_birth_date", "profile_sex"):
            assert sensors[key]["name"]
        assert set(sensors["profile_sex"]["state"]) == set(const.SEXES)
    data = {
        const.CONF_HEIGHT_CM: 170,
        const.CONF_BIRTH_DATE: "1985-03-07",
        const.CONF_SEX: "female",
    }
    assert up.profile_field(data, "height_cm") == 170
    assert up.profile_field(data, "birth_date") == date(1985, 3, 7)
    assert up.profile_field(data, "sex") == "female"
    assert up.profile_field({}, "sex") is None
