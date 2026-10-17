"""Pure helpers for the per-user profile stored in "user" config subentries.

Kept free of Home Assistant imports so the validation and migration logic can
be unit-tested on its own.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from .const import (
    CONF_BIRTH_DATE,
    CONF_BIRTH_YEAR,
    CONF_EXPECTED_WEIGHT_KG,
    CONF_HEIGHT_CM,
    CONF_SEX,
    CONF_SLOT,
    CONF_USER_NAME,
    DEFAULT_BIRTH_YEAR,
    DEFAULT_HEIGHT_CM,
    DEFAULT_SEX,
    MAX_EXPECTED_WEIGHT_KG,
    MAX_HEIGHT_CM,
    MIN_BIRTH_YEAR,
    MIN_EXPECTED_WEIGHT_KG,
    MIN_HEIGHT_CM,
    SEXES,
)

# Keys that moved from the config entry (data/options) into the user subentry.
LEGACY_PROFILE_KEYS: tuple[str, ...] = (CONF_HEIGHT_CM, CONF_BIRTH_YEAR, CONF_SEX)

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


def profile_from_data(data: Mapping[str, Any]) -> UserProfile:
    """Read a user profile from subentry data, falling back to defaults."""
    try:
        height = int(data.get(CONF_HEIGHT_CM, DEFAULT_HEIGHT_CM))
    except (TypeError, ValueError):
        height = DEFAULT_HEIGHT_CM
    birth = parse_birth_date(data.get(CONF_BIRTH_DATE)) or date(DEFAULT_BIRTH_YEAR, 1, 1)
    sex = str(data.get(CONF_SEX, DEFAULT_SEX))
    return UserProfile(height_cm=height, birth_date=birth, sex=sex)


def default_profile() -> UserProfile:
    """Profile used when no user has been configured."""
    return profile_from_data({})


def primary_user_data(users: Iterable[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """Return the data of the user in the lowest slot, or None without users."""

    def slot(item: Mapping[str, Any]) -> int:
        try:
            return int(item.get(CONF_SLOT, 0))
        except (TypeError, ValueError):
            return 0

    return min(users, key=slot, default=None)


@dataclass(frozen=True)
class MigrationResult:
    """Outcome of the v1 -> v2 config entry migration."""

    user_title: str
    user_data: dict[str, Any]
    entry_data: dict[str, Any]
    entry_options: dict[str, Any]


def migrate_v1_to_v2(
    data: Mapping[str, Any], options: Mapping[str, Any]
) -> MigrationResult:
    """Split the single-user profile out of a v1 entry.

    Options take precedence over data, like the v1 runtime lookups did. Missing
    or malformed values fall back to the defaults. The user is always named
    "User 1" (the entry title is the scale's name, not a person's).
    """

    def current(key: str, default: Any) -> Any:
        return options.get(key, data.get(key, default))

    try:
        height = int(current(CONF_HEIGHT_CM, DEFAULT_HEIGHT_CM))
    except (TypeError, ValueError):
        height = DEFAULT_HEIGHT_CM
    height = min(MAX_HEIGHT_CM, max(MIN_HEIGHT_CM, height))

    try:
        birth_year = int(current(CONF_BIRTH_YEAR, DEFAULT_BIRTH_YEAR))
    except (TypeError, ValueError):
        birth_year = DEFAULT_BIRTH_YEAR
    if not 1 <= birth_year <= 9999:
        birth_year = DEFAULT_BIRTH_YEAR

    sex = str(current(CONF_SEX, DEFAULT_SEX)).lower()
    if sex not in SEXES:
        sex = DEFAULT_SEX

    name = DEFAULT_USER_NAME
    return MigrationResult(
        user_title=name,
        user_data={
            CONF_USER_NAME: name,
            CONF_HEIGHT_CM: height,
            CONF_BIRTH_DATE: f"{birth_year:04d}-01-01",
            CONF_SEX: sex,
            CONF_SLOT: 1,
        },
        entry_data={k: v for k, v in data.items() if k not in LEGACY_PROFILE_KEYS},
        entry_options={k: v for k, v in options.items() if k not in LEGACY_PROFILE_KEYS},
    )


def legacy_entity_unique_ids(address: str) -> tuple[tuple[str, str], ...]:
    """Return ``(platform, unique_id)`` of the v1 profile entities to remove."""
    return (
        ("number", f"{address}_height_cm"),
        ("number", f"{address}_birth_year"),
        ("select", f"{address}_sex"),
    )
