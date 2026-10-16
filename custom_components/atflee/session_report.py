"""The breakdown of one BLE session, as the diagnostic sensors publish it.

``SessionTrace`` records where the session spent its time and where it died.
``blesession`` turns that into the shared report -- which radio the link went
over, and one sentence on what a failure most likely means. The sentences
specific to the scale live here; the ones every BLE device shares (a proxy
with no free slot, a weak signal, a stack that stopped answering) come from
the library.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from blesession import Failure, WriteTimeout, build_report, cause_key, placement, stages
from blesession import SessionTrace as _SessionTrace
from blesession.hass import radio_facts

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Device stage -> the shared stage the report and the generic sentences use.
# ``arm`` is the start-measurement / user-info handshake after the link is up;
# ``measure`` is the wait for measurement packets.
ARM = "arm"
MEASURE = "measure"
STAGE_MAP: dict[str, str] = {
    ARM: stages.SESSION,
    MEASURE: stages.TRANSFER,
}

_NO_STAGE_CAUSE = "The session failed before the first stage was reached; see error."


class SessionTrace(_SessionTrace):
    """A session trace that already knows the scale's stage names."""

    def __init__(self) -> None:
        super().__init__(STAGE_MAP)


def scale_cause(
    stage: str | None,
    detail: str | None,
    error: str,
    facts: Mapping[str, Any],
) -> str | None:
    """The scale's own reading of a failure, or None where the shared one is it."""
    where = detail or stage
    advice = placement(facts, noun="scale")
    if where == stages.CONNECT:
        # "slot" is the same on every proxy; the shared sentence covers it.
        if "slot" in error.lower():
            return None
        return (
            "The BLE link could not be established. The scale keeps its radio "
            "off until someone steps on it, so this is its normal state when "
            f"it sleeps; a weigh-in that never connects is different.{advice}"
        )
    if where == ARM:
        return (
            "Connected, but the scale did not take the start-measurement or "
            "user-info writes: the link dropped, or the phone app holds the "
            f"scale.{advice}"
        )
    if where == MEASURE:
        return (
            "The link dropped while waiting for measurement packets: the "
            f"scale went back to sleep or the signal is weak.{advice}"
        )
    return None


def build_session_report(
    hass: HomeAssistant,
    address: str,
    *,
    operation: str,
    trace: SessionTrace | None,
    exc: BaseException | None,
) -> dict[str, Any]:
    """Assemble the attributes for one finished session."""
    trace = trace if trace is not None else SessionTrace()

    def cause(failure: Failure) -> str | None:
        """The scale's sentence; ``None`` hands the failure back to the library."""
        if isinstance(failure.exc, WriteTimeout):
            return None
        text = scale_cause(failure.stage, failure.detail, failure.error, failure.facts)
        if text is not None:
            return text
        if cause_key(failure.stage, failure.error, exc=failure.exc) is not None:
            return None
        return _NO_STAGE_CAUSE

    return build_report(
        operation=operation,
        trace=trace,
        exc=exc,
        facts=radio_facts(hass, address, trace.link),
        cause=cause,
        noun="scale",
    )
