"""Packet utilities for Atflee BLE protocol."""

from __future__ import annotations

from dataclasses import dataclass


FRAME_HEADER = b"\x55\x55"
FRAME_TAIL = b"\xAA\xAA"

# Atflee BLE wire layout (one 20-byte frame, both directions):
#   byte 0:      package index (rolling counter chosen by the sender)
#   byte 1:      total message length in bytes, including the command byte
#   byte 2:      frame index (0 for the first frame, 1.. for continuations)
#   bytes 3..18: 16 data bytes, zero padded; data[0] is the command
#   byte 19:     checksum = (sum of the 16 data bytes & 0x1F) | (unit << 5)
# A message longer than 16 bytes spans several frames that share byte 0/1.
PROTOCOL_VER = 0x07  # byte 1 of every 7-byte message such as the A2 weight packet
FRAME_LEN = 20
FRAME_DATA_LEN = 16

# Encode (app -> scale) commands.
CMD_REPLY_ACK = 0xB0  # app ack to A1/A3/A4/A5/A7 messages
CMD_USER_INFO = 0xB1

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

# Messages the scale retransmits until the app replies with a B0 ack.
ACKED_COMMANDS = frozenset(
    {
        CMD_DEVICE_INFO,
        CMD_WEIGHT_STABLE,
        CMD_HISTORY,
        CMD_UPLOAD_RESULT,
        CMD_UPLOAD_RESULT_EX,
    }
)


def frame_checksum(data: bytes, unit: int = 0) -> int:
    """Checksum byte for one frame's 16 data bytes."""
    return ((sum(data) & 0x1F) | ((unit & 0x7) << 5)) & 0xFF


def build_frames(
    command: int, payload: bytes, *, pkg_index: int, unit: int = 0
) -> list[bytes]:
    """Split a command message into 20-byte frames."""
    message = bytes([command & 0xFF]) + payload
    if len(message) > 0xFF:
        raise ValueError("message too long")
    frame_count = max(1, -(-len(message) // FRAME_DATA_LEN))
    padded = message.ljust(frame_count * FRAME_DATA_LEN, b"\x00")
    frames: list[bytes] = []
    for index in range(frame_count):
        chunk = padded[index * FRAME_DATA_LEN : (index + 1) * FRAME_DATA_LEN]
        frames.append(
            bytes([pkg_index & 0xFF, len(message), index])
            + chunk
            + bytes([frame_checksum(chunk, unit)])
        )
    return frames


@dataclass(slots=True)
class AtfleeMessage:
    """One reassembled scale -> app message."""

    pkg_index: int
    command: int
    data: bytes  # bytes after the command byte
    unit: int = 0


class FrameAssembler:
    """Reassemble multi-frame messages from validated 20-byte frames."""

    def __init__(self) -> None:
        self._pkg_index: int | None = None
        self._length = 0
        self._next_frame = 0
        self._buffer = bytearray()
        self._unit = 0

    def reset(self) -> None:
        self._pkg_index = None
        self._length = 0
        self._next_frame = 0
        self._buffer = bytearray()

    def feed(self, frame: bytes) -> AtfleeMessage | None:
        """Add one frame; return the message once it is complete."""
        if len(frame) != FRAME_LEN:
            return None
        data = frame[3:19]
        if (sum(data) & 0x1F) != (frame[19] & 0x1F):
            return None
        pkg_index, length, index = frame[0], frame[1], frame[2]
        if length == 0:
            return None
        if index == 0:
            self.reset()
            self._pkg_index = pkg_index
            self._length = length
            self._unit = frame[19] >> 5
        elif (
            self._pkg_index != pkg_index
            or self._length != length
            or index != self._next_frame
        ):
            return None
        self._buffer += data
        self._next_frame = index + 1
        if len(self._buffer) < length:
            return None
        message = AtfleeMessage(
            pkg_index=self._pkg_index,
            command=self._buffer[0],
            data=bytes(self._buffer[1:length]),
            unit=self._unit,
        )
        self.reset()
        return message


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
