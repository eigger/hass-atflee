"""Protocol parser helpers for Atflee BLE notifications."""

from __future__ import annotations

import json
import logging
from typing import Any

from .models import AtfleeMeasurement
from .packet import parse_frame
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
        if cmd in (0xA2, 0xA3):
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
                parsed.is_stable = cmd == 0xA3
                parsed.is_body_composition_complete = False
                parsed.packet_command = cmd
                parsed.packet_sequence = packet_seq
                parsed.packet_tail = packet_tail
                parsed.extended_payload_hex = extended_slice.hex() if extended_slice else None
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


def build_user_info_packet(user_index: int, sex: str, age: int, height_cm: int) -> bytes:
    """Builds a B1 user info packet for active body composition measurement.
    
    Byte 0: 0xB1 (Command)
    Byte 1: 0x01 (Package index or user index)
    Byte 2: user_index
    Byte 3: sex (1=Male, 0=Female)
    Byte 4: age
    Byte 5: height (cm)
    ...
    Byte 13: XOR Checksum
    """
    packet = bytearray(14)
    packet[0] = 0xB1
    packet[1] = 0x01
    packet[2] = max(1, user_index & 0xFF)
    packet[3] = 1 if str(sex).lower() in ("male", "m", "1") else 0
    packet[4] = age & 0xFF
    packet[5] = height_cm & 0xFF
    
    # Calculate checksum (Simple XOR)
    checksum = 0
    for i in range(1, 13):
        checksum ^= packet[i]
    packet[13] = checksum
    
    return bytes(packet)


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
