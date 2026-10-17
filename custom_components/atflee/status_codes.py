"""Readable states for the scale's numeric status codes (no Home Assistant).

Only codes whose meaning is backed by captured packets get a name; any other
code maps to ``other`` and the number itself stays available as the sensor's
``raw`` attribute, so an unexpected code is never hidden or misnamed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

OTHER = "other"

# Byte 1 of the A2 (unstable weight) message, the byte right after the
# command. It is only sent while the weight is still settling, and every
# captured A2 packet carries 1; no other value has been observed.
MEASURE_STATUS_STATES: Mapping[int, str] = {1: "weighing"}


def status_options(states: Mapping[int, str]) -> list[str]:
    """ENUM options for a code table: its named states, then ``other``."""
    return [*dict.fromkeys(states.values()), OTHER]


def status_state(code: int | None, states: Mapping[int, str]) -> str | None:
    """Readable state for a status code; None when no code was received."""
    if code is None:
        return None
    return states.get(code, OTHER)


def restored_status(value: Any, states: Mapping[int, str]) -> str | None:
    """State to restore from a stored value.

    Accepts a state slug (current versions) or the plain number stored by
    versions that showed the raw code, so an upgrade keeps a readable state
    instead of an invalid ENUM value.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if text in status_options(states):
            return text
        try:
            value = float(text)
        except ValueError:
            return None
    if isinstance(value, float):
        if not value.is_integer():
            return None
        value = int(value)
    if isinstance(value, int):
        return status_state(value, states)
    return None
