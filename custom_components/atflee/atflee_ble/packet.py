"""Packet utilities for Atflee BLE protocol."""

from __future__ import annotations

from dataclasses import dataclass


FRAME_HEADER = b"\x55\x55"
FRAME_TAIL = b"\xAA\xAA"

# Atflee BLE wire layout (observed on iGripX FFB2 notifies):
#   byte 0: sequence (0x01, 0x02, ...)
#   byte 1: protocol version (0x07 for base, 0x6c for v2)
#   byte 2: reserved / sub-length
#   byte 3: command byte (0xA0-0xA8, 0xBD for decode; 0xB0-0xC1, 0xFFA0 for encode)
#   bytes 4..18: payload (up to 15 bytes)
#   byte 19: checksum (XOR of bytes [1..18])
PROTOCOL_VER = 0x07
PACKET_LEN = 20
CHECKSUM_INDEX = 19

# Encode (app -> scale) commands.
CMD_REPLY_ACK = 0xB0  # app ack to a scale-initiated A0 reply_package request
CMD_USER_INFO = 0xB1
CMD_SETTINGS = 0xB2
CMD_START_MEASURE = 0xFFA0  # broadcast control: 0x01 = start, 0x00 = stop

# Decode (scale -> app) commands.
CMD_REPLY_PACKAGE = 0xA0
CMD_DEVICE_INFO = 0xA1
CMD_WEIGHT_UNSTABLE = 0xA2
CMD_WEIGHT_STABLE = 0xA3
CMD_HISTORY = 0xA4
CMD_UPLOAD_RESULT = 0xA5
CMD_BATTERY = 0xA6
CMD_UPLOAD_RESULT_EX = 0xA7
CMD_STATUS = 0xA8


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


def xor_checksum(data: bytes) -> int:
    """XOR checksum used by the Atflee BLE packet trailer."""
    value = 0
    for byte in data:
        value ^= byte
    return value & 0xFF


def build_packet(seq: int, command: int, payload: bytes = b"") -> bytes:
    """Build a 20-byte command packet with XOR checksum.

    seq is the rolling sequence (1..255). command is the encode command byte
    (0xB1 for user info, etc.). payload is zero-padded to 15 bytes.
    """
    if len(payload) > PACKET_LEN - 5:
        raise ValueError("payload too large for command packet")

    packet = bytearray(PACKET_LEN)
    packet[0] = seq & 0xFF
    packet[1] = PROTOCOL_VER
    packet[2] = 0x00
    packet[3] = command & 0xFF
    packet[4 : 4 + len(payload)] = payload
    packet[CHECKSUM_INDEX] = xor_checksum(bytes(packet[1:CHECKSUM_INDEX]))
    return bytes(packet)


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
