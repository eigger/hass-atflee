"""Protocol parser helpers for Atflee BLE notifications."""

from __future__ import annotations

import json
import logging
from typing import Any

from .models import AtfleeMeasurement
from .packet import (
    CMD_REPLY_ACK,
    CMD_REPLY_PACKAGE,
    CMD_START_MEASURE,
    CMD_USER_INFO,
    CMD_UPLOAD_RESULT,
    CMD_UPLOAD_RESULT_EX,
    CMD_WEIGHT_STABLE,
    CMD_WEIGHT_UNSTABLE,
    build_packet,
    parse_frame,
)
from .protocol_spec import NATIVE_MEASUREMENT_KEYS

_LOGGER = logging.getLogger(__name__)


def parse_measurement_packet(payload: bytes) -> AtfleeMeasurement:
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
    # Here, weight is encoded in 3-byte big-endian at [6:9]:
    #   0x011774 -> 71540 -> 71.54 kg (divide by 1000).
    if len(framed_payload) >= 9:
        cmd = framed_payload[3]
        # A0: scale-initiated reply_package request. The scale waits for a
        # matching B0 ack before progressing past the weight stage, so we
        # surface it as a control packet (no measurement fields) and let the
        # coordinator send the ack.
        if cmd == CMD_REPLY_PACKAGE:
            parsed.packet_command = cmd
            parsed.packet_sequence = framed_payload[0]
            parsed.packet_sub_index = framed_payload[4] if len(framed_payload) > 4 else None
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
            _decode_body_composition_result(framed_payload, parsed)
            return parsed
        if cmd in (CMD_WEIGHT_UNSTABLE, CMD_WEIGHT_STABLE):
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


def build_user_info_packet(
    user_index: int,
    sex: str,
    age: int,
    height_cm: int,
    *,
    seq: int = 1,
    target_weight_kg: float = 0.0,
    body_type: int = 0,
    unit: int = 0,
) -> bytes:
    """Build a 20-byte 0xB1 user info packet.

    Layout matches the [seq, 0x07, 0x00, cmd] header observed on the A2/A3
    notify side, followed by a 15-byte payload and XOR checksum.

    Payload layout (offsets from packet[4]):
        +0..+1: user_id big-endian
        +2:    sex (1 = male, 0 = female)
        +3:    age (years)
        +4:    height cm
        +5:    body_type (0 = ordinary, 1 = athlete)
        +6..+7: target weight in 0.01 kg, big-endian
        +8:    unit (0 = kg, 1 = lb, 2 = st)
    """

    payload = bytearray(15)
    user_id = max(1, user_index) & 0xFFFF
    payload[0] = (user_id >> 8) & 0xFF
    payload[1] = user_id & 0xFF
    payload[2] = 1 if str(sex).lower() in ("male", "m", "1") else 0
    payload[3] = max(0, min(120, int(age))) & 0xFF
    payload[4] = max(0, min(250, int(height_cm))) & 0xFF
    payload[5] = body_type & 0xFF
    target_units = max(0, int(round(target_weight_kg * 100)))
    payload[6] = (target_units >> 8) & 0xFF
    payload[7] = target_units & 0xFF
    payload[8] = unit & 0xFF
    return build_packet(seq=seq, command=CMD_USER_INFO, payload=bytes(payload))


def build_start_measure_packet(*, seq: int = 1) -> bytes:
    """Build the FFA0 control packet that arms the active measurement.

    The scale needs an explicit FFA0 0x01 control to begin an active body
    composition measurement after the user info exchange. FFA0 0x00 is the
    matching stop command.
    """
    payload = bytes([0x01])
    return build_packet(seq=seq, command=CMD_START_MEASURE & 0xFF, payload=payload)


def build_stop_measure_packet(*, seq: int = 1) -> bytes:
    """Build the FFA0 0x00 control packet that ends the active measurement."""
    return build_packet(
        seq=seq, command=CMD_START_MEASURE & 0xFF, payload=bytes([0x00])
    )


def build_reply_ack_packet(
    *, seq: int, echo_index: int = 0, payload_bytes: bytes = b""
) -> bytes:
    """Build a 0xB0 reply that acknowledges a scale-initiated A0 packet.

    The scale's A0 carries a sub-index in payload[0]; the B0 reply echoes that
    sub-index so the firmware knows which request we are answering. Optional
    payload_bytes are placed right after the echoed index for cases where the
    firmware also wants a small response body (e.g. setting confirmation).
    """
    payload = bytearray(15)
    payload[0] = echo_index & 0xFF
    if payload_bytes:
        room = len(payload) - 1
        payload[1 : 1 + min(room, len(payload_bytes))] = payload_bytes[:room]
    return build_packet(seq=seq, command=CMD_REPLY_ACK, payload=bytes(payload))


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
