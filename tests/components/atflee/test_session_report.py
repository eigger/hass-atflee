"""Tests for the session report helpers."""

from __future__ import annotations


from blesession import SessionReports, fallback_report, stages

from custom_components.atflee import session_report


def test_stage_map_uses_shared_stages() -> None:
    trace = session_report.SessionTrace()
    trace.fail(session_report.ARM)
    assert trace.failed_primary == stages.SESSION
    assert trace.failed_detail == session_report.ARM


def test_scale_cause_per_stage() -> None:
    cause = session_report.scale_cause
    assert "link could not be established" in cause(stages.CONNECT, None, "boom", {})
    assert cause(stages.CONNECT, None, "no free slot", {}) is None
    assert "preparing the measurement" in cause(
        stages.SESSION, session_report.ARM, "x", {}
    )
    assert "measurement packet" in cause(
        stages.TRANSFER, session_report.MEASURE, "x", {}
    )
    assert cause(None, None, "x", {}) is None


def test_failure_counts_and_survives_success() -> None:
    reports = SessionReports()
    reports.record(fallback_report("measure", exc=TimeoutError("connect")))
    reports.record(fallback_report("measure", exc=None))
    assert reports.failures == 1
    assert reports.last_failure is not None
    assert reports.last_failure_at is not None
    assert reports.last["success"] is True


def _report(trace, exc):
    # hass=None: radio_facts never raises, it just yields no radio facts.
    return session_report.build_session_report(
        None, "AA:BB:CC:DD:EE:FF", operation="measure", trace=trace, exc=exc
    )


def test_build_report_connect_failure() -> None:
    trace = session_report.SessionTrace()
    try:
        with trace.timed(stages.CONNECT):
            raise TimeoutError("link down")
    except TimeoutError as exc:
        report = _report(trace, exc)
    assert report["success"] is False
    assert report["failed_stage"] == stages.CONNECT
    assert "link could not be established" in report["likely_cause"]


def test_build_report_arm_failure_and_unstaged_failure() -> None:
    trace = session_report.SessionTrace()
    trace.fail(session_report.ARM)
    report = _report(trace, ValueError("bad birth year"))
    assert report["failed_stage"] == stages.SESSION
    assert report["failed_detail"] == session_report.ARM
    assert "preparing the measurement" in report["likely_cause"]

    report = _report(session_report.SessionTrace(), RuntimeError("boom"))
    assert report["likely_cause"]


def test_build_report_success() -> None:
    trace = session_report.SessionTrace()
    trace.record(session_report.MEASURE, 1.5)
    report = _report(trace, None)
    assert report["success"] is True
    assert "error" not in report
