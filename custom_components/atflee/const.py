"""Constants for the Atflee integration."""

from __future__ import annotations

DOMAIN = "atflee"

CONF_NOTIFY_TIMEOUT_SECONDS = "notify_timeout_seconds"
CONF_HEIGHT_CM = "height_cm"
CONF_SEX = "sex"
CONF_ENABLE_BODY_COMP = "enable_body_composition"

# Per-user profile keys, stored in the data of a "user" config subentry.
SUBENTRY_TYPE_USER = "user"
CONF_USER_NAME = "name"
CONF_BIRTH_DATE = "birth_date"
CONF_SLOT = "slot"
CONF_EXPECTED_WEIGHT_KG = "expected_weight_kg"
SEXES: tuple[str, ...] = ("male", "female")
MIN_EXPECTED_WEIGHT_KG = 10
MAX_EXPECTED_WEIGHT_KG = 300

DEFAULT_NOTIFY_TIMEOUT_SECONDS = 12
DEFAULT_HEIGHT_CM = 170
DEFAULT_SEX = "male"
DEFAULT_ENABLE_BODY_COMP = False
MIN_HEIGHT_CM = 80
MAX_HEIGHT_CM = 250
MIN_BIRTH_YEAR = 1900


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
