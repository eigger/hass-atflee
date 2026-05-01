"""Constants for the Atflee integration."""

from __future__ import annotations

DOMAIN = "atflee"

CONF_NOTIFY_TIMEOUT_SECONDS = "notify_timeout_seconds"
CONF_HEIGHT_CM = "height_cm"
CONF_BIRTH_YEAR = "birth_year"
CONF_SEX = "sex"
CONF_ENABLE_BODY_COMP = "enable_body_composition"

DEFAULT_NOTIFY_TIMEOUT_SECONDS = 12
DEFAULT_HEIGHT_CM = 170
DEFAULT_BIRTH_YEAR = 1990
DEFAULT_SEX = "male"
DEFAULT_ENABLE_BODY_COMP = False
MIN_HEIGHT_CM = 80
MAX_HEIGHT_CM = 250
MIN_BIRTH_YEAR = 1900
MAX_BIRTH_YEAR = 2026


# - Advertisement explicitly contained 0xFFB0 and 0x1530 services.
# - Keep iGripX (FFB0) first, then previous fallbacks.
GATT_PROFILES: tuple[tuple[str, str, str | None], ...] = (
    # iGripX/JC780 devices often expose notify on FFB2 and write on FFB1.
    (
        "0000ffb0-0000-1000-8000-00805f9b34fb",
        "0000ffb2-0000-1000-8000-00805f9b34fb",
        "0000ffb1-0000-1000-8000-00805f9b34fb",
    ),
    # Fallback for variants that notify on FFB1.
    (
        "0000ffb0-0000-1000-8000-00805f9b34fb",
        "0000ffb1-0000-1000-8000-00805f9b34fb",
        "0000ffb2-0000-1000-8000-00805f9b34fb",
    ),
    (
        "0000fff0-0000-1000-8000-00805f9b34fb",
        "0000fff1-0000-1000-8000-00805f9b34fb",
        "0000fff1-0000-1000-8000-00805f9b34fb",
    ),
    (
        "0000ffe0-0000-1000-8000-00805f9b34fb",
        "0000ffe1-0000-1000-8000-00805f9b34fb",
        "0000ffe1-0000-1000-8000-00805f9b34fb",
    ),
)

# Additional channels observed on iGripX/JC780 devices.
OPTIONAL_NOTIFY_UUIDS: tuple[str, ...] = (
    "0000ffb3-0000-1000-8000-00805f9b34fb",
    "00001531-1212-efde-1523-785feabcd123",
)

DEBUG_READ_UUIDS: tuple[str, ...] = (
    "00001534-1212-efde-1523-785feabcd123",
)
