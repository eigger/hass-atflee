"""Pure helpers for the per-user profile stored in "user" config subentries.

Kept free of Home Assistant imports so the validation logic can
be unit-tested on its own.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from .const import (
    CONF_BIRTH_DATE,
    CONF_EXPECTED_WEIGHT_KG,
    CONF_HEIGHT_CM,
    CONF_SEX,
    CONF_SLOT,
    CONF_USER_NAME,
    MAX_EXPECTED_WEIGHT_KG,
    MAX_HEIGHT_CM,
    MIN_BIRTH_YEAR,
    MIN_EXPECTED_WEIGHT_KG,
    MIN_HEIGHT_CM,
    SEXES,
)

DEFAULT_USER_NAME = "User 1"


def parse_birth_date(value: Any) -> date | None:
    """Parse an ISO ``YYYY-MM-DD`` string (or a date) into a date."""
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def lowest_free_slot(used: Iterable[int]) -> int:
    """Return the lowest positive slot number not in ``used``."""
    taken = set(used)
    slot = 1
    while slot in taken:
        slot += 1
    return slot


def validate_user_input(
    data: Mapping[str, Any],
    today: date,
    existing_names: Iterable[str] = (),
) -> dict[str, str]:
    """Return ``{field: error_key}`` for a user form submission (empty = valid)."""
    errors: dict[str, str] = {}

    name = str(data.get(CONF_USER_NAME, "")).strip()
    if not name:
        errors[CONF_USER_NAME] = "name_required"
    elif name.casefold() in {n.strip().casefold() for n in existing_names}:
        errors[CONF_USER_NAME] = "name_exists"

    try:
        height = float(data.get(CONF_HEIGHT_CM))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        height = None
    if height is None or not MIN_HEIGHT_CM <= height <= MAX_HEIGHT_CM:
        errors[CONF_HEIGHT_CM] = "invalid_height"

    birth = parse_birth_date(data.get(CONF_BIRTH_DATE))
    if birth is None:
        errors[CONF_BIRTH_DATE] = "invalid_birth_date"
    elif birth > today:
        errors[CONF_BIRTH_DATE] = "birth_date_in_future"
    elif birth.year < MIN_BIRTH_YEAR:
        errors[CONF_BIRTH_DATE] = "birth_date_too_old"

    if data.get(CONF_SEX) not in SEXES:
        errors[CONF_SEX] = "invalid_sex"

    expected = data.get(CONF_EXPECTED_WEIGHT_KG)
    if expected is not None:
        try:
            valid = MIN_EXPECTED_WEIGHT_KG <= float(expected) <= MAX_EXPECTED_WEIGHT_KG
        except (TypeError, ValueError):
            valid = False
        if not valid:
            errors[CONF_EXPECTED_WEIGHT_KG] = "invalid_expected_weight"

    return errors


def normalize_user_input(data: Mapping[str, Any], slot: int) -> dict[str, Any]:
    """Build the subentry data dict from a validated form submission."""
    result: dict[str, Any] = {
        CONF_USER_NAME: str(data[CONF_USER_NAME]).strip(),
        CONF_HEIGHT_CM: int(round(float(data[CONF_HEIGHT_CM]))),
        CONF_BIRTH_DATE: parse_birth_date(data[CONF_BIRTH_DATE]).isoformat(),  # type: ignore[union-attr]
        CONF_SEX: data[CONF_SEX],
        CONF_SLOT: slot,
    }
    expected = data.get(CONF_EXPECTED_WEIGHT_KG)
    if expected is not None:
        result[CONF_EXPECTED_WEIGHT_KG] = float(expected)
    return result


@dataclass(frozen=True)
class UserProfile:
    """Body parameters of one user, with the birth date still unresolved to an age."""

    height_cm: int
    birth_date: date
    sex: str


def profile_from_data(data: Mapping[str, Any]) -> UserProfile | None:
    """Read a user profile from subentry data, or None if it is unusable."""
    try:
        height = int(data[CONF_HEIGHT_CM])
    except (KeyError, TypeError, ValueError):
        return None
    birth = parse_birth_date(data.get(CONF_BIRTH_DATE))
    sex = data.get(CONF_SEX)
    if birth is None or sex not in SEXES or height <= 0:
        return None
    return UserProfile(height_cm=height, birth_date=birth, sex=sex)


def _slot(item: Mapping[str, Any]) -> int:
    try:
        return int(item.get(CONF_SLOT, 0))
    except (TypeError, ValueError):
        return 0


def primary_user_data(users: Iterable[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """Return the data of the user in the lowest slot, or None without users."""
    return min(users, key=_slot, default=None)


def primary_user_id(users: Mapping[str, Mapping[str, Any]]) -> str | None:
    """Return the subentry id of the user in the lowest slot, or None without users."""
    return min(users, key=lambda sid: (_slot(users[sid]), sid), default=None)


def user_unique_id(address: str, subentry_id: str, key: str) -> str:
    """Unique id of a per-user entity."""
    return f"{address}_{subentry_id}_{key}"


def user_device_identifier(address: str, subentry_id: str) -> str:
    """Device identifier value of a user device (the domain is added by the caller)."""
    return f"{address}_{subentry_id}"
