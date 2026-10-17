"""Pure helpers for the per-user profile stored in "user" config subentries.

Kept free of Home Assistant imports so the validation logic can
be unit-tested on its own.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from time import monotonic
from typing import Any

from .const import (
    ACTIVE_USER_AUTO,
    ACTIVE_USER_TIMEOUT_SECONDS,
    ASSIGNMENT_DEFAULT,
    ASSIGNMENT_FALLBACK,
    ASSIGNMENT_MATCHED,
    ASSIGNMENT_SELECTED,
    ASSIGNMENT_UNASSIGNED,
    CONF_BIRTH_DATE,
    CONF_EXPECTED_WEIGHT_KG,
    CONF_HEIGHT_CM,
    CONF_SEX,
    CONF_SLOT,
    CONF_USER_NAME,
    DEFAULT_FALLBACK_MAX_DELTA_KG,
    DEFAULT_MATCH_TOLERANCE_KG,
    MATCH_MARGIN_KG,
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


def user_slot(item: Mapping[str, Any]) -> int:
    try:
        return int(item.get(CONF_SLOT, 0))
    except (TypeError, ValueError):
        return 0


def primary_user_id(users: Mapping[str, Mapping[str, Any]]) -> str | None:
    """Return the subentry id of the user in the lowest slot, or None without users."""
    return min(users, key=lambda sid: (user_slot(users[sid]), sid), default=None)


def resolve_user_id(
    users: Mapping[str, Mapping[str, Any]],
    active_id: str | None,
    default_id: str | None,
) -> str | None:
    """Pick the user: the selected one, else the default, else the lowest slot.

    Ids that no longer exist are skipped; None only when there are no users.
    """
    if active_id in users:
        return active_id
    if default_id in users:
        return default_id
    return primary_user_id(users)


@dataclass(frozen=True)
class Candidate:
    """A user considered for a measured weight."""

    user_id: str
    reference_kg: float
    delta_kg: float  # absolute distance to the measured weight


@dataclass(frozen=True)
class Attribution:
    """Who a session's measurement belongs to, and how that was decided.

    ``assignment`` is one of the ``ASSIGNMENT_*`` values; ``user_id`` is None only
    when it is ``unassigned`` (or there are no users at all). ``reason`` explains
    why identification failed (fallback / unassigned), ``candidates`` are the
    users that had a reference weight, nearest first.
    """

    assignment: str
    user_id: str | None
    reason: str | None = None
    candidates: tuple[Candidate, ...] = ()


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def reference_weight(
    user: Mapping[str, Any], last_weight: Any = None
) -> float | None:
    """A user's reference weight: the last measured one, else the expected one."""
    last = _float_or_none(last_weight)
    return last if last is not None else _float_or_none(user.get(CONF_EXPECTED_WEIGHT_KG))


def attribute_weight(
    weight_kg: float,
    users: Mapping[str, Mapping[str, Any]],
    last_weights: Mapping[str, float],
    *,
    active_id: str | None = None,
    default_id: str | None = None,
    tolerance_kg: float = DEFAULT_MATCH_TOLERANCE_KG,
    margin_kg: float = MATCH_MARGIN_KG,
    fallback_max_delta_kg: float = DEFAULT_FALLBACK_MAX_DELTA_KG,
) -> Attribution:
    """Decide whose measurement a weight is.

    A selected user always wins and a lone user is always that user. Otherwise
    the user whose reference weight is nearest is taken if it is within
    ``tolerance_kg`` and at least ``margin_kg`` closer than the runner-up. If that
    fails, the default user is assumed, unless the weight is more than
    ``fallback_max_delta_kg`` away from the default user's reference weight; then
    the measurement belongs to nobody.
    """
    if not users:
        return Attribution(ASSIGNMENT_UNASSIGNED, None, "no_users")
    if active_id in users:
        return Attribution(ASSIGNMENT_SELECTED, active_id)
    if len(users) == 1:
        return Attribution(ASSIGNMENT_DEFAULT, next(iter(users)))

    candidates: list[Candidate] = []
    for sid, data in users.items():
        ref = reference_weight(data, last_weights.get(sid))
        if ref is not None:
            candidates.append(Candidate(sid, ref, round(abs(weight_kg - ref), 3)))
    candidates.sort(key=lambda c: (c.delta_kg, user_slot(users[c.user_id]), c.user_id))
    ranked = tuple(candidates)

    reason: str | None
    if not ranked:
        reason = "no_candidates"
    elif ranked[0].delta_kg > tolerance_kg:
        reason = "out_of_tolerance"
    elif len(ranked) > 1 and ranked[1].delta_kg - ranked[0].delta_kg < margin_kg:
        reason = "ambiguous"
    else:
        return Attribution(ASSIGNMENT_MATCHED, ranked[0].user_id, candidates=ranked)

    fallback_id = resolve_user_id(users, None, default_id)
    fallback_ref = reference_weight(users[fallback_id], last_weights.get(fallback_id))
    if fallback_ref is not None and abs(weight_kg - fallback_ref) > fallback_max_delta_kg:
        return Attribution(ASSIGNMENT_UNASSIGNED, None, reason, ranked)
    return Attribution(ASSIGNMENT_FALLBACK, fallback_id, reason, ranked)


class SessionAttributor:
    """Decides once per session whose measurement it is.

    The scale reports a ramp of unstable weights while someone steps on, so the
    decision waits for the first stable weight. Until then ``attribution`` is
    None and nothing is locked.
    """

    def __init__(self) -> None:
        self.attribution: Attribution | None = None

    def reset(self) -> None:
        self.attribution = None

    def observe(
        self,
        weight_kg: float | None,
        is_stable: bool | None,
        users: Mapping[str, Mapping[str, Any]],
        last_weights: Mapping[str, float],
        **kwargs: Any,
    ) -> Attribution | None:
        """Return the new attribution at the deciding packet, else None."""
        if self.attribution is not None or not users:
            return None
        if not is_stable or not weight_kg or weight_kg <= 0:
            return None
        self.attribution = attribute_weight(weight_kg, users, last_weights, **kwargs)
        return self.attribution


def should_store_weight(
    assignment: str | None, user: Mapping[str, Any], stored_weight: Any
) -> bool:
    """Whether a stable weight becomes the user's reference weight.

    A fallback assignment is only a guess, so it may seed a user who has no
    reference at all but never overwrites one.
    """
    if assignment == ASSIGNMENT_FALLBACK:
        return reference_weight(user, stored_weight) is None
    return assignment in (ASSIGNMENT_MATCHED, ASSIGNMENT_SELECTED, ASSIGNMENT_DEFAULT)


def sanitize_last_weights(raw: Any, users: Iterable[str]) -> dict[str, float]:
    """Keep only valid stored weights of users that still exist."""
    if not isinstance(raw, Mapping):
        return {}
    keep = set(users)
    result: dict[str, float] = {}
    for sid, value in raw.items():
        weight = _float_or_none(value)
        if sid in keep and weight is not None:
            result[sid] = weight
    return result


def user_option_labels(users: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    """Return ``{subentry_id: label}`` for the active-user select, in slot order.

    Labels are the user names. Duplicate names (or a name equal to the "auto"
    option) get a numeric suffix so every label maps back to one user.
    """
    labels: dict[str, str] = {}
    taken = {ACTIVE_USER_AUTO}
    for sid in sorted(users, key=lambda s: (user_slot(users[s]), s)):
        base = str(users[sid].get(CONF_USER_NAME) or "").strip() or sid
        label, n = base, 1
        while label in taken:
            n += 1
            label = f"{base} ({n})"
        taken.add(label)
        labels[sid] = label
    return labels


class ActiveUserSelection:
    """The user picked on the select, valid for one session or a time limit.

    Pure state with an injectable clock; the coordinator owns the real timer and
    calls ``clear`` when a session consumed the selection.
    """

    def __init__(
        self,
        timeout: float = ACTIVE_USER_TIMEOUT_SECONDS,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._timeout = timeout
        self._clock = clock
        self._user_id: str | None = None
        self._selected_at = 0.0

    @property
    def timeout(self) -> float:
        return self._timeout

    @property
    def user_id(self) -> str | None:
        """The selected subentry id, or None (auto) when unset or expired."""
        if self._user_id is not None and self._clock() - self._selected_at >= self._timeout:
            self._user_id = None
        return self._user_id

    def select(self, user_id: str | None) -> None:
        """Select a user (None = auto) and restart the timeout."""
        self._user_id = user_id
        self._selected_at = self._clock()

    def clear(self) -> None:
        self._user_id = None


def user_unique_id(address: str, subentry_id: str, key: str) -> str:
    """Unique id of a per-user entity."""
    return f"{address}_{subentry_id}_{key}"


def user_device_identifier(address: str, subentry_id: str) -> str:
    """Device identifier value of a user device (the domain is added by the caller)."""
    return f"{address}_{subentry_id}"


def reload_needed(
    old_users: Mapping[str, Any],
    new_users: Mapping[str, Any],
    old_options: Mapping[str, Any],
    new_options: Mapping[str, Any],
    live_option_keys: Iterable[str] = (),
) -> bool:
    """Decide whether an entry update requires a reload.

    Users changing always does. Options do too, except the ``live_option_keys``
    that the coordinator reads at use time.
    """
    if old_users != new_users:
        return True
    live = set(live_option_keys)
    strip = lambda o: {k: v for k, v in o.items() if k not in live}  # noqa: E731
    return strip(old_options) != strip(new_options)
