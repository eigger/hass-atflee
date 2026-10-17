"""Tests for the age helper, B1 user index and A7 user id."""

from __future__ import annotations

from datetime import date

import custom_components.atflee.atflee_ble.packet as packet
import custom_components.atflee.atflee_ble.profile as profile
import custom_components.atflee.atflee_ble.protocol as protocol

age_from_birth_date = profile.age_from_birth_date


def test_age_birthday_boundary() -> None:
    birth = date(1990, 6, 15)
    assert age_from_birth_date(birth, date(2026, 6, 14)) == 35
    assert age_from_birth_date(birth, date(2026, 6, 15)) == 36
    assert age_from_birth_date(birth, date(2026, 12, 31)) == 36


def test_age_feb_29_birthday() -> None:
    birth = date(2000, 2, 29)
    assert age_from_birth_date(birth, date(2025, 2, 28)) == 24
    assert age_from_birth_date(birth, date(2025, 3, 1)) == 25
    assert age_from_birth_date(birth, date(2024, 2, 28)) == 23
    assert age_from_birth_date(birth, date(2024, 2, 29)) == 24


def test_age_clamped_to_zero() -> None:
    assert age_from_birth_date(date(2030, 1, 1), date(2026, 1, 1)) == 0


def _b1(**kwargs) -> bytes:
    frames = protocol.build_user_info_frames(
        sex="male", age=40, height_cm=175, pkg_index=3, timestamp=1700000000, **kwargs
    )
    assert len(frames) == 1
    return frames[0]


def test_b1_default_user_index_is_one() -> None:
    frame = _b1()
    assert frame == _b1(user_index=1)
    # frame: pkg, len, idx, cmd, time(4), offset(2), user_index, height
    assert frame[3] == packet.CMD_USER_INFO
    assert frame[10] == 1
    assert frame[11] == 175


def test_b1_user_index_byte() -> None:
    assert _b1(user_index=2)[10] == 2
    assert _b1(user_index=255)[10] == 255
    assert _b1(user_index=0)[10] == 1
    assert _b1(user_index=999)[10] == 255
    # only the user index byte (and the checksum) differ
    a, b = _b1(user_index=1), _b1(user_index=2)
    assert [i for i in range(len(a)) if a[i] != b[i]] == [10, 19]


def _a7(user_id: int | None, *, count: int = 2, with_flag: bool = True) -> bytes:
    data = (
        (1700000000).to_bytes(4, "big")
        + (70000).to_bytes(4, "big")
        + bytes([72, count])
        + b"".join((5000 + i).to_bytes(2, "big") for i in range(count))
    )
    if user_id is not None:
        data += user_id.to_bytes(4, "big")
        if with_flag:
            data += bytes([0])
    return data


def _parse(data: bytes):
    msg = packet.AtfleeMessage(
        pkg_index=1, command=packet.CMD_UPLOAD_RESULT_EX, data=data
    )
    return protocol.parse_message(msg, None)


def test_a7_user_id_parsed() -> None:
    parsed = _parse(_a7(0x01020304))
    assert parsed.user_id == 0x01020304
    assert parsed.heart_rate == 72
    assert parsed.weight_kg is not None


def test_a7_user_id_absent_when_truncated() -> None:
    assert _parse(_a7(None)).user_id is None
    assert _parse(_a7(None)[:-1]).user_id is None


def test_user_id_defaults_to_none() -> None:
    from custom_components.atflee.atflee_ble import models

    assert models.AtfleeMeasurement().user_id is None
