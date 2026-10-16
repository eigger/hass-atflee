"""Tests for the session report helpers (no Home Assistant required)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from blesession import SessionReports, fallback_report, stages

_SPEC = importlib.util.spec_from_file_location(
    "atflee_session_report",
    Path(__file__).parents[1] / "custom_components" / "atflee" / "session_report.py",
)
session_report = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(session_report)


def test_stage_map_uses_shared_stages() -> None:
    trace = session_report.SessionTrace()
    trace.fail(session_report.ARM)
    assert trace.failed_primary == stages.SESSION
    assert trace.failed_detail == session_report.ARM


def test_scale_cause_per_stage() -> None:
    cause = session_report.scale_cause
    assert "link could not be established" in cause(stages.CONNECT, None, "boom", {})
    assert cause(stages.CONNECT, None, "no free slot", {}) is None
    assert "start-measurement" in cause(stages.SESSION, session_report.ARM, "x", {})
    assert "waiting for measurement" in cause(stages.TRANSFER, session_report.MEASURE, "x", {})
    assert cause(None, None, "x", {}) is None


def test_failure_counts_and_survives_success() -> None:
    reports = SessionReports()
    reports.record(fallback_report("measure", exc=TimeoutError("connect")))
    reports.record(fallback_report("measure", exc=None))
    assert reports.failures == 1
    assert reports.last_failure is not None
    assert reports.last_failure_at is not None
    assert reports.last["success"] is True
