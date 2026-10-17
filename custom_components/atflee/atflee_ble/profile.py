"""User profile helpers shared by the scale protocol and the integration."""

from __future__ import annotations

from datetime import date


def age_from_birth_date(birth: date, today: date) -> int:
    """Return the completed years between ``birth`` and ``today`` (never negative).

    A birthday on 29 February counts on 1 March in non-leap years.
    """
    month, day = birth.month, birth.day
    if (month, day) == (2, 29) and not _is_leap(today.year):
        month, day = 3, 1
    age = today.year - birth.year - ((today.month, today.day) < (month, day))
    return max(0, age)


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
