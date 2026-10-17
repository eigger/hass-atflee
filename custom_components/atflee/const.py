"""Constants for the Atflee integration."""

from __future__ import annotations

DOMAIN = "atflee"

CONF_NOTIFY_TIMEOUT_SECONDS = "notify_timeout_seconds"
CONF_HEIGHT_CM = "height_cm"
CONF_SEX = "sex"
CONF_ENABLE_BODY_COMP = "enable_body_composition"
# Scale-level option: subentry id of the user assumed when nobody is selected.
CONF_DEFAULT_USER = "default_user"

# Scale-level options for weight-based user identification (auto mode).
CONF_MATCH_TOLERANCE_KG = "match_tolerance_kg"
CONF_FALLBACK_MAX_DELTA_KG = "fallback_max_delta_kg"
DEFAULT_MATCH_TOLERANCE_KG = 3.0
MIN_MATCH_TOLERANCE_KG = 0.5
MAX_MATCH_TOLERANCE_KG = 10.0
DEFAULT_FALLBACK_MAX_DELTA_KG = 15.0
MIN_FALLBACK_MAX_DELTA_KG = 5.0
MAX_FALLBACK_MAX_DELTA_KG = 100.0
# The best candidate must be this much closer than the runner-up.
MATCH_MARGIN_KG = 1.5

# Fired when a weight fits nobody and is too far from the default user too.
EVENT_UNASSIGNED_MEASUREMENT = "atflee_unassigned_measurement"

# How a measurement was attributed (``assignment`` state attribute).
ASSIGNMENT_SELECTED = "selected"  # picked on the Active user select
ASSIGNMENT_MATCHED = "matched"  # identified by weight
ASSIGNMENT_FALLBACK = "fallback"  # not identifiable, default user assumed
ASSIGNMENT_DEFAULT = "default"  # only one user, nothing to decide
ASSIGNMENT_UNASSIGNED = "unassigned"  # written to nobody

LAST_WEIGHTS_STORE_VERSION = 1
LAST_WEIGHTS_SAVE_DELAY_SECONDS = 10

# State of the "Active user" select meaning "no explicit selection".
ACTIVE_USER_AUTO = "auto"
# The selection falls back to auto after this long if no session consumed it.
ACTIVE_USER_TIMEOUT_SECONDS = 600

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

# Standard Device Information service (0x180A): AtfleeHardwareInfo field -> char.
DEVICE_INFORMATION_CHARS: tuple[tuple[str, str], ...] = (
    ("manufacturer", "00002a29-0000-1000-8000-00805f9b34fb"),
    ("model", "00002a24-0000-1000-8000-00805f9b34fb"),
    ("serial_number", "00002a25-0000-1000-8000-00805f9b34fb"),
    ("hardware_revision", "00002a27-0000-1000-8000-00805f9b34fb"),
    ("firmware_revision", "00002a26-0000-1000-8000-00805f9b34fb"),
    ("software_revision", "00002a28-0000-1000-8000-00805f9b34fb"),
)
DEVICE_INFORMATION_READ_TIMEOUT_SECONDS = 1.5

DEBUG_READ_UUIDS: tuple[str, ...] = ("00001534-1212-efde-1523-785feabcd123",)
