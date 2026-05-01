"""Core BLE package for Atflee integration."""

from .connection import AtfleeBleClient
from .models import AtfleeMeasurement, AtfleeState
from .packet import AtfleeFrame, crc16_modbus, parse_frame
from .protocol import parse_measurement_packet
from .protocol_spec import ATFLEE_CANDIDATE_FAMILIES, NATIVE_MEASUREMENT_KEYS

__all__ = [
    "AtfleeBleClient",
    "AtfleeFrame",
    "AtfleeMeasurement",
    "AtfleeState",
    "ATFLEE_CANDIDATE_FAMILIES",
    "NATIVE_MEASUREMENT_KEYS",
    "crc16_modbus",
    "parse_frame",
    "parse_measurement_packet",
]
