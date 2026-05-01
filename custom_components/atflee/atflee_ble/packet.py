"""Packet utilities for Atflee BLE protocol."""

from __future__ import annotations

from dataclasses import dataclass


FRAME_HEADER = b"\x55\x55"
FRAME_TAIL = b"\xAA\xAA"


@dataclass(slots=True)
class AtfleeFrame:
    """Parsed frame structure used by Atflee-like protocols."""

    command: int
    payload: bytes
    checksum: int | None = None
    is_valid: bool = True


def crc16_modbus(data: bytes) -> int:
    """Compute CRC16-Modbus (poly 0xA001)."""

    crc = 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def parse_frame(data: bytes) -> AtfleeFrame | None:
    """Parse one frame: 55 55 <cmd> <len> <payload...> <crc?> aa aa.

    This is a tolerant parser for Atflee protocol frames:
    - accepts frames with or without explicit CRC bytes
    - validates CRC when present (2-byte little-endian at frame tail before 0xAA 0xAA)
    """

    if len(data) < 6:
        return None
    if not data.startswith(FRAME_HEADER) or not data.endswith(FRAME_TAIL):
        return None

    command = data[2]
    payload_len = data[3]
    body = data[4:-2]  # drop header/cmd/len and frame tail

    if len(body) < payload_len:
        return None

    payload = body[:payload_len]
    checksum: int | None = None
    is_valid = True

    trailing = body[payload_len:]
    if len(trailing) >= 2:
        checksum = int.from_bytes(trailing[:2], byteorder="little", signed=False)
        computed = crc16_modbus(bytes([command, payload_len]) + payload)
        is_valid = checksum == computed

    return AtfleeFrame(
        command=command,
        payload=payload,
        checksum=checksum,
        is_valid=is_valid,
    )
