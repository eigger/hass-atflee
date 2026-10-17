"""Readable status code states and their translations."""

from __future__ import annotations

from pathlib import Path

import json

import pytest

import custom_components.atflee.status_codes as sc
import custom_components.atflee.atflee_ble.protocol as protocol

STATES = sc.MEASURE_STATUS_STATES


_DIR = Path(__file__).parents[3] / "custom_components" / "atflee"


def test_options_end_with_other() -> None:
    assert sc.status_options(STATES) == ["weighing", "other"]
    assert sc.status_options({}) == ["other"]


@pytest.mark.parametrize(
    ("code", "state"),
    [(None, None), (1, "weighing"), (0, "other"), (2, "other"), (255, "other")],
)
def test_status_state(code, state) -> None:
    assert sc.status_state(code, STATES) == state


@pytest.mark.parametrize(
    ("stored", "state"),
    [
        (None, None),
        ("weighing", "weighing"),
        ("other", "other"),
        # Numbers stored by versions that showed the raw code.
        ("1", "weighing"),
        ("1.0", "weighing"),
        (1, "weighing"),
        (1.0, "weighing"),
        ("3", "other"),
        (3, "other"),
        # Not a code: nothing to restore.
        ("unknown", None),
        ("unavailable", None),
        ("", None),
        ("1.5", None),
        (1.5, None),
        (True, None),
    ],
)
def test_restored_status(stored, state) -> None:
    assert sc.restored_status(stored, STATES) == state


def test_every_state_is_translated() -> None:
    for path in (
        _DIR / "strings.json",
        _DIR / "translations" / "en.json",
        _DIR / "translations" / "ko.json",
    ):
        sensors = json.loads(path.read_text(encoding="utf-8"))["entity"]["sensor"]
        assert set(sensors["measure_status"]["state"]) == set(sc.status_options(STATES))


def test_a2_packet_code_maps_to_weighing() -> None:
    # Captured unstable weight frame: byte 4 (after the A2 command) is 1.
    parsed = protocol.parse_measurement_packet(
        bytes.fromhex("010700a201190117740000000000000000000008")
    )
    assert parsed.is_stable is False
    assert parsed.measure_status == 1
    assert sc.status_state(parsed.measure_status, STATES) == "weighing"
