"""Protocol parser helpers for Atflee BLE notifications."""

from __future__ import annotations

import json
import logging
import struct
from typing import Any

from .models import AtfleeDeviceInfo, AtfleeMeasurement
from .packet import (
    CMD_DEVICE_INFO,
    CMD_HISTORY,
    CMD_REPLY_ACK,
    CMD_REPLY_PACKAGE,
    CMD_USER_INFO,
    CMD_UPLOAD_RESULT,
    CMD_UPLOAD_RESULT_EX,
    CMD_WEIGHT_STABLE,
    CMD_WEIGHT_UNSTABLE,
    PROTOCOL_VER,
    AtfleeMessage,
    build_frames,
    parse_frame,
)
from .protocol_spec import NATIVE_MEASUREMENT_KEYS

_LOGGER = logging.getLogger(__name__)


def parse_measurement_packet(payload: bytes, kg_division: int = 0) -> AtfleeMeasurement:
    """Parse a notification payload into a normalized measurement model.

    The Atflee packet format varies by device firmware. This parser
    accepts known practical formats and preserves raw hex for diagnostics.
    """

    framed_payload = payload
    frame = parse_frame(payload)
    if frame is not None:
        # Prefer extracted payload body from framed packets.
        framed_payload = frame.payload
        _LOGGER.debug(
            "Atflee frame parsed: cmd=0x%02X payload_len=%d checksum=%s valid=%s raw=%s",
            frame.command,
            len(frame.payload),
            f"0x{frame.checksum:04X}" if frame.checksum is not None else None,
            frame.is_valid,
            payload.hex(),
        )
    else:
        _LOGGER.debug(
            "Atflee frame parse miss: raw_len=%d raw=%s",
            len(payload),
            payload.hex(),
        )

    raw_hex = payload.hex()
    parsed = AtfleeMeasurement(raw_hex=raw_hex)

    # Pattern 1: UTF-8 JSON payload (e.g. {"weight":70.2,"bodyFat":18.4}).
    try:
        decoded = framed_payload.decode("utf-8").strip()
        if decoded.startswith("{") and decoded.endswith("}"):
            obj = json.loads(decoded)
            _fill_from_mapping(parsed, obj)
            return parsed

        # Pattern 2: simple key-value CSV payload (e.g. weight=70.2,bmi=23.4).
        if "=" in decoded and "," in decoded:
            pairs: dict[str, Any] = {}
            for item in decoded.split(","):
                if "=" not in item:
                    continue
                key, value = item.split("=", 1)
                pairs[key.strip()] = value.strip()
            _fill_from_mapping(parsed, pairs)
            return parsed
    except UnicodeDecodeError:
        pass
    except (ValueError, json.JSONDecodeError):
        pass

    # Pattern 2.5: iGripX/JC780 notify packet (20 bytes, command at index 3).
    # Observed examples:
    #   010700a201190117740000000000000000000008
    #   020700a201190117740000000000000000000008
    # Here the A2 weight word is the big-endian 32-bit value at [5..8]
    # (0x19011774): the low 18 bits are grams (0x11774 -> 71540 -> 71.54 kg).
    if len(framed_payload) >= 9:
        cmd = framed_payload[3]
        # A0: the scale's reply to a message we sent (reply_package). It is
        # surfaced as a control packet (no measurement fields) and not acked.
        if cmd == CMD_REPLY_PACKAGE:
            parsed.packet_command = cmd
            parsed.packet_sequence = framed_payload[0]
            parsed.packet_tail = (
                framed_payload[19] if len(framed_payload) > 19 else None
            )
            parsed.extended_payload_hex = (
                framed_payload[4:19].hex()
                if len(framed_payload) >= 19
                else framed_payload[4:].hex()
            )
            parsed.measure_state = "handshake"
            return parsed
        # A5/A7: body composition / impedance result. Firmware variants may
        # shift offsets; we record the raw extended bytes regardless so an
        # unparsable layout still surfaces in diagnostics.
        if cmd in (CMD_UPLOAD_RESULT, CMD_UPLOAD_RESULT_EX):
            if framed_payload[1] == PROTOCOL_VER:
                if not _decode_upload_packet(framed_payload, parsed, kg_division):
                    _mark_control_packet(framed_payload, parsed)
                return parsed
            _decode_body_composition_result(framed_payload, parsed)
            return parsed
        if cmd in (CMD_WEIGHT_UNSTABLE, CMD_WEIGHT_STABLE):
            if framed_payload[1] == PROTOCOL_VER:
                # Known layout: never guess a weight from bytes that belong to
                # other fields when the decoded one is implausible.
                if not _decode_weight_packet(framed_payload, cmd, parsed, kg_division):
                    _mark_control_packet(framed_payload, parsed)
                return parsed
            # Other firmware variants (byte 1 != 0x07) keep the legacy probing.
            # Device firmware variants use different 3-byte BE offsets for weight.
            # Known candidates:
            # - [6:9] (legacy captures: 0x011774 -> 71.54kg)
            # - [5:8] (current ffb3 captures: 0x0116A2 -> 71.33kg)
            weight_candidates: list[tuple[int, int, float]] = []
            for start in (6, 5):
                end = start + 3
                if len(framed_payload) < end:
                    continue
                raw = int.from_bytes(framed_payload[start:end], byteorder="big", signed=False)
                kg = raw / 1000.0
                weight_candidates.append((start, raw, kg))

            chosen_start: int | None = None
            weight_raw_3b = 0
            weight_kg_3b = 0.0
            for start, raw, kg in weight_candidates:
                if 10.0 <= kg <= 300.0:
                    chosen_start = start
                    weight_raw_3b = raw
                    weight_kg_3b = kg
                    break

            if chosen_start is None and weight_candidates:
                # Keep debug visibility even when no plausible weight exists.
                chosen_start, weight_raw_3b, weight_kg_3b = weight_candidates[0]
            packet_seq = framed_payload[0] if len(framed_payload) > 0 else None
            packet_tail = framed_payload[19] if len(framed_payload) > 19 else None
            extended_slice = (
                framed_payload[9:19] if len(framed_payload) >= 19 else framed_payload[9:]
            )
            extended_non_zero = [idx + 9 for idx, value in enumerate(extended_slice) if value != 0]
            _LOGGER.debug(
                (
                    "Atflee A2/A3 packet parsed: cmd=0x%02X seq=%s raw3b=%d "
                    "weight=%.2f weight_offset=%s tail=%s ext_nonzero_idx=%s payload=%s"
                ),
                cmd,
                packet_seq,
                weight_raw_3b,
                weight_kg_3b,
                chosen_start,
                packet_tail,
                ",".join(str(i) for i in extended_non_zero) if extended_non_zero else "none",
                framed_payload.hex(),
            )
            if extended_non_zero:
                _LOGGER.debug(
                    "Atflee A2/A3 extended bytes (possible extra sensors): hex=%s",
                    extended_slice.hex(),
                )
            if 10.0 <= weight_kg_3b <= 300.0:
                parsed.weight_kg = round(weight_kg_3b, 2)
                parsed.measure_state = "weight"
                parsed.is_stable = cmd == CMD_WEIGHT_STABLE
                parsed.is_body_composition_complete = False
                parsed.packet_command = cmd
                parsed.packet_sequence = packet_seq
                parsed.packet_tail = packet_tail
                parsed.extended_payload_hex = extended_slice.hex() if extended_slice else None

                # Some firmware variants ship impedance bytes inside the A3
                # (stable weight) tail. Surface them so the body composition
                # algorithm path can pick them up if present.
                if cmd == CMD_WEIGHT_STABLE and extended_non_zero:
                    _extract_inline_impedance(framed_payload, parsed)
                return parsed

    # Pattern 3: fallback heuristic for binary payload where first 2 bytes
    # often represent weight*10 in little-endian on many BLE scales.
    # To avoid false positives (e.g. protocol headers interpreted as weight),
    # only use this fallback for very short payloads.
    if 2 <= len(framed_payload) <= 4:
        weight_raw = int.from_bytes(
            framed_payload[0:2], byteorder="little", signed=False
        )
        weight_kg = weight_raw / 10.0
        weight_kg_div100 = weight_raw / 100.0
        _LOGGER.debug(
            "Atflee fallback weight candidates: raw=%d /10=%.2f /100=%.2f payload=%s",
            weight_raw,
            weight_kg,
            weight_kg_div100,
            framed_payload.hex(),
        )
        if 10.0 <= weight_kg <= 300.0:
            parsed.weight_kg = weight_kg
            parsed.measure_state = "weight"
    elif len(framed_payload) > 4:
        _LOGGER.debug(
            "Atflee fallback skipped for long payload len=%d payload=%s",
            len(framed_payload),
            framed_payload.hex(),
        )

    if parsed.body_fat_pct is not None or parsed.impedance_ohm is not None:
        parsed.measure_state = "body_composition"
        parsed.is_stable = True
        parsed.is_body_composition_complete = True
    elif parsed.weight_kg is not None:
        parsed.measure_state = "weight"
        parsed.is_body_composition_complete = False
    _apply_status_heuristics(parsed)

    return parsed


def _fill_from_mapping(measurement: AtfleeMeasurement, source: dict[str, Any]) -> None:
    """Fill model values from key variants used across clients."""

    # --- 기본 체중 ---
    measurement.weight_kg = _to_float(
        _pick(source, "weight", "weight_kg", "kg", "body_weight", "w")
    )
    measurement.weight_lb = _to_float(_pick(source, "weight_lb"))
    measurement.weight_st = _to_float(_pick(source, "weight_st"))

    # --- 기본 체성분 ---
    measurement.body_fat_pct = _to_float(
        _pick(source, "body_fat", "bodyFat", "fat", "fat_pct", "pbf", "fatRate", "bfr")
    )
    measurement.bmi = _to_float(_pick(source, "bmi"))
    measurement.impedance_ohm = _to_int(_pick(source, "impedance", "z", "impedance_ohm"))

    # --- 확장 체성분 ---
    measurement.subcutaneous_fat_pct = _to_float(
        _pick(source, "subcutaneousFat", "subcutfat", "subcutaneous_fat_pct")
    )
    measurement.visceral_fat = _to_float(
        _pick(source, "visceralFat", "vfal", "visceral_fat")
    )
    measurement.muscle_pct = _to_float(
        _pick(source, "muscle", "musclePercent", "muscle_pct")
    )
    measurement.muscle_mass = _to_float(
        _pick(source, "muscleMass", "muscle_mass")
    )
    measurement.bmr = _to_int(_pick(source, "bmr"))
    measurement.bone_mass = _to_float(
        _pick(source, "bone", "boneMass", "bone_mass")
    )
    measurement.moisture_pct = _to_float(
        _pick(source, "moisture", "moisturePercent", "water", "moisture_pct")
    )
    measurement.protein_pct = _to_float(
        _pick(source, "proteinRate", "protein", "proteinPercent", "protein_pct")
    )
    measurement.skeletal_muscle_pct = _to_float(
        _pick(source, "sm", "smPercent", "skeletal_muscle_pct")
    )
    measurement.physical_age = _to_int(
        _pick(source, "bodyage", "physicalAge", "physical_age")
    )
    measurement.body_score = _to_float(_pick(source, "bodyScore", "body_score"))

    # --- 기기 상태 ---
    measurement.battery_pct = _to_int(_pick(source, "battery", "batteryLevel", "battery_pct"))
    measurement.verify_status = _to_int(_pick(source, "verifyStatus"))
    measurement.measure_status = _to_int(_pick(source, "measure_status", "measureState"))
    measurement.scale_status = _to_int(_pick(source, "scale_status"))
    measurement.heart_rate = _to_int(_pick(source, "heart_rate"))
    measurement.support_upload_bodyfat = _to_bool(
        _pick(source, "support_upload_bodyfat")
    )

    # When native key names are present, infer that this is decoded map output.
    # This helps distinguish from ad-hoc fallback decoding.
    if any(key in source for key in NATIVE_MEASUREMENT_KEYS):
        _LOGGER.debug("Atflee native-map keys detected: %s", sorted(source.keys()))
        if measurement.measure_state is None:
            measurement.measure_state = _infer_measure_state(measurement)
        _apply_status_heuristics(measurement)


def _infer_measure_state(measurement: AtfleeMeasurement) -> str | None:
    if measurement.verify_status is not None:
        if measurement.verify_status == 0:
            return "weight"
        return "body_composition"
    if measurement.measure_status is not None and measurement.measure_status > 0:
        return "measuring"
    if (
        measurement.body_fat_pct is not None
        or measurement.impedance_ohm is not None
        or measurement.subcutaneous_fat_pct is not None
        or measurement.visceral_fat is not None
        or measurement.muscle_pct is not None
        or measurement.bone_mass is not None
    ):
        return "body_composition"
    if measurement.weight_kg is not None:
        return "weight"
    return None


def _apply_status_heuristics(measurement: AtfleeMeasurement) -> None:
    if measurement.is_stable is None:
        # Most devices report stable after verify/body-composition stages.
        measurement.is_stable = measurement.verify_status in (1, 2) or bool(
            measurement.body_fat_pct is not None or measurement.impedance_ohm is not None
        )
    if not measurement.is_body_composition_complete:
        measurement.is_body_composition_complete = measurement.verify_status in (1, 2)


def _pick(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in source:
            return source[key]
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_user_info_frames(
    *,
    sex: str,
    age: int,
    height_cm: int,
    pkg_index: int,
    timestamp: int,
    utc_offset_seconds: int = 0,
    user_index: int = 1,
    weight_kg: float = 0.0,
    target_weight_kg: float = 0.0,
    function_flags: int = 0x01,
    lang: int = 0,
) -> list[bytes]:
    """Build the B1 user-info message (one frame).

    Payload: time(4, unix s) utc_offset(2, minutes, bit15 = negative)
    user_index height weight*100(2) age|male<<7 function_flags
    target_weight*100(2) lang. ``function_flags`` bit0 enables impedance.
    """
    offset_minutes = abs(utc_offset_seconds) // 60
    if utc_offset_seconds < 0:
        offset_minutes |= 0x8000
    is_male = str(sex).lower() in ("male", "m", "1")
    age_byte = (max(0, min(120, int(age))) & 0x7F) | (0x80 if is_male else 0)
    payload = (
        (int(timestamp) & 0xFFFFFFFF).to_bytes(4, "big")
        + (offset_minutes & 0xFFFF).to_bytes(2, "big")
        + bytes([max(1, min(255, int(user_index))), max(0, min(250, int(height_cm)))])
        + (max(0, int(weight_kg * 100)) & 0xFFFF).to_bytes(2, "big")
        + bytes([age_byte, function_flags & 0xFF])
        + (max(0, int(target_weight_kg * 100)) & 0xFFFF).to_bytes(2, "big")
        + bytes([lang & 0xFF])
    )
    return build_frames(CMD_USER_INFO, payload, pkg_index=pkg_index)


def build_reply_frames(
    *, pkg_index: int, reply_index: int, state: int = 0
) -> list[bytes]:
    """Build the B0 ack for a received message.

    ``reply_index`` is byte 0 (package index) of the message being answered;
    ``state`` 0 means success.
    """
    return build_frames(
        CMD_REPLY_ACK,
        bytes([reply_index & 0xFF, state & 0xFF]),
        pkg_index=pkg_index,
    )



# Weight word shared by A2/A3/A5/A7 packets (big-endian 32-bit):
#   bits 0..17   weight in grams
#   bits 18..20  kg rounding code (0 = round to 10 g)
#   bits 24..31  body-fat algorithm type
_WEIGHT_MASK = 0x3FFFF


def _f32(value: float) -> float:
    """Round a Python float to single precision like the firmware math."""
    return struct.unpack("f", struct.pack("f", value))[0]


def _word_to_kg(word: int, division: int = 0) -> float:
    """Convert a packed weight word to kg using the scale's rounding rules.

    The rounding code in the word wins; when it is 0 the division reported by
    the device-info message (``division``) applies.
    """
    grams = float(word & _WEIGHT_MASK)
    code = ((word >> 18) & 0x7) or (division & 0x7)
    kg = _f32(grams / 1000.0)
    if code > 4:
        return kg
    scaled = _f32(kg * (1000.0 if code < 3 else 100.0))
    # The firmware nudges values whose next decimal digit is 9 upwards.
    if int(_f32(scaled * 10.0)) % 10 >= 9:
        scaled = _f32(scaled + 1.0)
    value = int(scaled)
    if code == 0:
        return int((value + 5) / 10.0) / 100.0
    if code in (1, 4):
        if value % 10 == 9:
            value += 10
        half = int(value / 10.0)
        half += half & 1
        return half / 100.0 if code == 1 else _f32(half / 10.0)
    if code == 2:
        tens = int((value + 20) / 10.0)
        base = (tens // 10) * 10
        return (base + 5 if tens % 10 >= 5 else base) / 100.0
    return _f32(int((value + 5) / 10.0) / 10.0)


def _plausible_impedance(raw: int) -> int | None:
    """Return ohms for a raw impedance short (some scales report ohm * 10)."""
    if 100 <= raw <= 1500:
        return raw
    # Scales flagged "impedance x10" report 1000-15000 for 100-1500 ohm;
    # anything up to 1500 is taken as plain ohms.
    if 1500 < raw <= 15000:
        return int(round(raw / 10.0))
    return None


def _decode_weight_packet(
    framed_payload: bytes, cmd: int, parsed: AtfleeMeasurement, kg_division: int = 0
) -> bool:
    """Decode A2 (unstable) / A3 (stable) weight packets.

    Payload layout (offsets in the 20-byte notification):
        A2: [4] state, [5..8] weight word, [9] heart rate
        A3: [4..7] weight word, [8] heart rate, [9..] impedance shorts
    Returns False when the layout does not yield a plausible weight so the
    caller can fall back to the legacy heuristics.
    """
    word_at = 5 if cmd == CMD_WEIGHT_UNSTABLE else 4
    if len(framed_payload) < word_at + 4:
        return False
    word = int.from_bytes(framed_payload[word_at : word_at + 4], "big")
    weight_kg = _word_to_kg(word, kg_division)
    if not 10.0 <= weight_kg <= 300.0:
        return False

    parsed.weight_kg = round(weight_kg, 2)
    parsed.packet_command = cmd
    parsed.packet_sequence = framed_payload[0]
    parsed.packet_tail = framed_payload[19] if len(framed_payload) > 19 else None
    parsed.extended_payload_hex = framed_payload[4:19].hex()
    parsed.measure_state = "weight"
    parsed.is_stable = cmd == CMD_WEIGHT_STABLE
    parsed.is_body_composition_complete = False

    hr_at = word_at + 4
    if len(framed_payload) > hr_at and framed_payload[hr_at]:
        parsed.heart_rate = framed_payload[hr_at]
    if cmd == CMD_WEIGHT_UNSTABLE and len(framed_payload) > 4:
        parsed.measure_status = framed_payload[4]
    if cmd == CMD_WEIGHT_STABLE:
        # The impedance count and scale come from the device-info packet,
        # which is not read here, so keep the conservative single-candidate
        # probe; A5/A7 carry an explicit count and are decoded exactly.
        _extract_inline_impedance(framed_payload, parsed)
    return True


def _decode_upload_packet(
    framed_payload: bytes, parsed: AtfleeMeasurement, kg_division: int = 0
) -> bool:
    """Decode the first frame of an A5/A7 measurement upload.

    Layout: [4..7] unix time, [8..11] weight word, [12] heart rate,
    [13] impedance count, [14..] impedance shorts. Fields that spill into
    later frames (user id, scale-computed body fat) are not read here.
    """
    if len(framed_payload) < 14:
        return False
    word = int.from_bytes(framed_payload[8:12], "big")
    weight_kg = _word_to_kg(word, kg_division)
    if not 10.0 <= weight_kg <= 300.0:
        return False

    cmd = framed_payload[3]
    parsed.packet_command = cmd
    parsed.packet_sequence = framed_payload[0]
    parsed.packet_tail = framed_payload[19] if len(framed_payload) > 19 else None
    parsed.extended_payload_hex = framed_payload[4:19].hex()
    parsed.weight_kg = round(weight_kg, 2)
    if framed_payload[12]:
        parsed.heart_rate = framed_payload[12]

    if framed_payload[13] and len(framed_payload) >= 16:
        ohm = _plausible_impedance(int.from_bytes(framed_payload[14:16], "big"))
        if ohm is not None:
            parsed.impedance_ohm = ohm

    parsed.measure_state = "body_composition"
    parsed.is_stable = True
    parsed.is_body_composition_complete = True
    return True


def parse_device_info(data: bytes) -> AtfleeDeviceInfo | None:
    """Decode the A1 device-info message body (bytes after the command)."""
    if len(data) < 9:
        return None
    word = int.from_bytes(data[0:4], "big")
    eight_electrode = bool(word >> 24 & 1)
    carry = word >> 29 & 1
    return AtfleeDeviceInfo(
        kg_division=word & 0x7,
        support_hr=bool(word >> 6 & 1),
        support_gravity=bool(word >> 7 & 1),
        support_balance=bool(word >> 8 & 1),
        eight_electrode=eight_electrode,
        freq_count=word >> 25 & 0x7,
        impedance_scaled=bool(word >> 28 & 1),
        impedance_count=(6 - carry) if eight_electrode else (carry + 1),
        function_flags=data[6],
        algorithm_type=data[5],
        protocol_ver=data[8],
    )


def _read_impedances(
    data: bytes, offset: int, count: int, scaled: bool
) -> tuple[float, ...]:
    values: list[float] = []
    for idx in range(count):
        start = offset + 2 * idx
        if start + 2 > len(data):
            break
        raw = int.from_bytes(data[start : start + 2], "big")
        values.append(raw / 10.0 if scaled else float(raw))
    return tuple(values)


def _apply_impedances(parsed: AtfleeMeasurement, values: tuple[float, ...]) -> None:
    parsed.impedances_ohm = values if any(values) else None
    if values and 0.0 < values[0] <= 3000.0:
        parsed.impedance_ohm = int(round(values[0]))


def parse_message(
    message: AtfleeMessage, device_info: AtfleeDeviceInfo | None
) -> AtfleeMeasurement | None:
    """Decode a validated A1/A3/A4/A5/A7 message; None for other commands.

    A3:     weight word(4) hr(1) impedance shorts
    A7:     time(4) weight word(4) hr(1) impedance count(1) impedance shorts
            user id(4) body-fat flag(1) [body fat * 10 (2)]
    A4/A5:  stored history records; acknowledged but never published as the
            live measurement.
    """
    cmd = message.command
    data = message.data
    division = device_info.kg_division if device_info else 0
    parsed = AtfleeMeasurement(raw_hex=(bytes([cmd]) + data).hex())
    parsed.packet_command = cmd
    parsed.packet_sequence = message.pkg_index
    parsed.extended_payload_hex = data.hex()
    scaled = bool(device_info and device_info.impedance_scaled)

    if cmd in (CMD_HISTORY, CMD_UPLOAD_RESULT, CMD_DEVICE_INFO):
        return parsed
    if cmd == CMD_WEIGHT_STABLE:
        if len(data) < 5:
            return parsed
        weight_kg = _word_to_kg(int.from_bytes(data[0:4], "big"), division)
        if not 10.0 <= weight_kg <= 300.0:
            return parsed
        parsed.weight_kg = round(weight_kg, 2)
        if data[4]:
            parsed.heart_rate = data[4]
        channels = (
            device_info.impedance_channels if device_info else (len(data) - 5) // 2
        )
        _apply_impedances(parsed, _read_impedances(data, 5, channels, scaled))
        parsed.measure_state = "weight"
        parsed.is_stable = True
        return parsed
    if cmd == CMD_UPLOAD_RESULT_EX:
        if len(data) < 10:
            return parsed
        weight_kg = _word_to_kg(int.from_bytes(data[4:8], "big"), division)
        if not 10.0 <= weight_kg <= 300.0:
            return parsed
        parsed.weight_kg = round(weight_kg, 2)
        if data[8]:
            parsed.heart_rate = data[8]
        count = data[9]
        _apply_impedances(parsed, _read_impedances(data, 10, count, scaled))
        pos = 10 + 2 * count
        if len(data) >= pos + 4:
            parsed.user_id = int.from_bytes(data[pos : pos + 4], "big")
        if len(data) >= pos + 7 and data[pos + 4]:
            body_fat = int.from_bytes(data[pos + 5 : pos + 7], "big") / 10.0
            if 2.0 <= body_fat <= 80.0:
                parsed.body_fat_pct = body_fat
        parsed.measure_state = "body_composition"
        parsed.is_stable = True
        parsed.is_body_composition_complete = True
        return parsed
    return None


def _mark_control_packet(framed_payload: bytes, parsed: AtfleeMeasurement) -> None:
    """Record packet metadata only, leaving every measurement field unset."""
    parsed.packet_command = framed_payload[3]
    parsed.packet_sequence = framed_payload[0]
    parsed.packet_tail = framed_payload[19] if len(framed_payload) > 19 else None
    parsed.extended_payload_hex = framed_payload[4:19].hex()


def _decode_body_composition_result(framed_payload: bytes, parsed: AtfleeMeasurement) -> None:
    """Decode an A5 / A7 body composition result packet.

    Unknown bytes are kept as None so the parser does not fabricate values
    when firmware diverges from the expected layout below.

    Offsets (relative to framed_payload):
        [3]   command (0xA5 / 0xA7)
        [4]   sequence sub-index
        [5..7]  weight in grams (3-byte big-endian, /1000 = kg)
        [8..9]  impedance ohm (big-endian)
        [10]  body fat (% * 10)
        [11]  body water (% * 10)
        [12]  muscle (% * 10)
        [13]  visceral fat (level * 10)
        [14]  bone mass (kg * 10)
        [15..16] BMR (kcal, big-endian)
        [17]  protein (% * 10)
        [18]  physical age (years)
    """
    cmd = framed_payload[3]
    parsed.packet_command = cmd
    parsed.packet_sequence = framed_payload[0] if len(framed_payload) > 0 else None
    parsed.packet_tail = framed_payload[19] if len(framed_payload) > 19 else None
    parsed.extended_payload_hex = (
        framed_payload[4:19].hex() if len(framed_payload) >= 19 else framed_payload[4:].hex()
    )

    if len(framed_payload) >= 8:
        weight_raw = int.from_bytes(framed_payload[5:8], byteorder="big", signed=False)
        weight_kg = weight_raw / 1000.0
        if 10.0 <= weight_kg <= 300.0:
            parsed.weight_kg = round(weight_kg, 2)

    if len(framed_payload) >= 10:
        impedance = int.from_bytes(framed_payload[8:10], byteorder="big", signed=False)
        if 100 <= impedance <= 1500:
            parsed.impedance_ohm = impedance

    parsed.body_fat_pct = _scaled_byte(framed_payload, 10, scale=10.0, lo=2.0, hi=80.0)
    parsed.moisture_pct = _scaled_byte(framed_payload, 11, scale=10.0, lo=10.0, hi=90.0)
    parsed.muscle_pct = _scaled_byte(framed_payload, 12, scale=10.0, lo=10.0, hi=80.0)
    parsed.visceral_fat = _scaled_byte(framed_payload, 13, scale=10.0, lo=1.0, hi=30.0)
    parsed.bone_mass = _scaled_byte(framed_payload, 14, scale=10.0, lo=0.5, hi=8.0)

    if len(framed_payload) >= 17:
        bmr_raw = int.from_bytes(framed_payload[15:17], byteorder="big", signed=False)
        if 500 <= bmr_raw <= 4000:
            parsed.bmr = bmr_raw

    parsed.protein_pct = _scaled_byte(framed_payload, 17, scale=10.0, lo=5.0, hi=40.0)

    if len(framed_payload) >= 19:
        age_raw = framed_payload[18]
        if 5 <= age_raw <= 120:
            parsed.physical_age = age_raw

    parsed.measure_state = "body_composition"
    parsed.is_stable = True
    # The A7 variant carries the closing "EX" upload — treat both as complete.
    parsed.is_body_composition_complete = True


def _extract_inline_impedance(framed_payload: bytes, parsed: AtfleeMeasurement) -> None:
    """Read impedance bytes that some firmwares append to the A3 tail.

    Heuristic: scan two-byte windows in [9..18] for a value in 100..1500.
    Only sets the field if a single plausible window is found.
    """
    if parsed.impedance_ohm is not None:
        return
    candidates: list[int] = []
    end = min(len(framed_payload) - 1, 18)
    for idx in range(9, end):
        value = int.from_bytes(framed_payload[idx : idx + 2], byteorder="big", signed=False)
        if 100 <= value <= 1500:
            candidates.append(value)
    if len(candidates) == 1:
        parsed.impedance_ohm = candidates[0]


def _scaled_byte(
    data: bytes, index: int, *, scale: float, lo: float, hi: float
) -> float | None:
    """Read one byte, divide by scale, return only if within [lo, hi]."""
    if len(data) <= index:
        return None
    raw = data[index]
    if raw == 0:
        return None
    value = raw / scale
    if lo <= value <= hi:
        return round(value, 2)
    return None


def _to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    return None
