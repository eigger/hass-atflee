"""Protocol specification for Atflee BLE scales."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProtocolFamily:
    """One protocol family and its decode/encode command groups."""

    protocol_ver: int
    decode_commands: tuple[str, ...]
    encode_commands: tuple[str, ...]


# Preferred order for Atflee/iGripX style body scales.
ATFLEE_CANDIDATE_FAMILIES: tuple[ProtocolFamily, ...] = (
    ProtocolFamily(
        protocol_ver=108,
        decode_commands=(
            "A0 reply_package",
            "A1 device_info",
            "A2 unstable_weight",
            "A3 stable_weight",
            "A4 weight_history",
            "A5/A7 upload_data",
            "A6 wifi_result",
            "A8 upload_userinfo_list",
            "BD file_status",
        ),
        encode_commands=(
            "B0 reply_package",
            "B1/B8/BA/BE/C0 user_info",
            "B2/B4/BB/BF/C1 user_info_list",
            "B5 config_wifi",
            "B6 set_ui_item_list",
            "BC file_info",
            "BD other_cmd",
            "FFA0 frame_data",
        ),
    ),
    ProtocolFamily(
        protocol_ver=107,
        decode_commands=(
            "A0 reply_package",
            "A1 device_info",
            "A2 unstable_weight",
            "A3 stable_weight",
            "A4 weight_history",
            "A5/A7 upload_data",
            "A6 wifi_result",
            "A8 upload_userinfo_list",
            "AD file_status",
        ),
        encode_commands=(
            "B0 reply_package",
            "B1/B8/BA/BE user_info",
            "B2/B4/BB/BF user_info_list",
            "B5 config_wifi",
            "B6 set_ui_item_list",
            "B7 config_server_url",
            "BC file_info",
            "BD other_cmd",
            "FFA0 frame_data",
        ),
    ),
    ProtocolFamily(
        protocol_ver=101,
        decode_commands=(
            "broadcast_weight",
            "broadcast_measure",
            "broadcast_temperature",
            "broadcast_coord/adc",
        ),
        encode_commands=(),
    ),
    ProtocolFamily(
        protocol_ver=102,
        decode_commands=("broadcast_bm15",),
        encode_commands=(),
    ),
)


# Common keys exposed by native decode output maps.
NATIVE_MEASUREMENT_KEYS: tuple[str, ...] = (
    # 기본
    "battery",
    "weight_g",
    "weight_kg",
    "weight_lb",
    "weight_st",
    "weight_st_lb",
    "measureState",
    "measure_status",
    "scale_status",
    "verifyStatus",
    "heart_rate",
    # 임피던스
    "imps",
    "imp_count",
    "imp_precision",
    "imp_property",
    "support_upload_bodyfat",
    # 체성분 기본
    "fatRate",
    "bmi",
    # 체성분 확장
    "subcutaneousFat",
    "visceralFat",
    "muscle",
    "moisture",
    "proteinRate",
    "bodyage",
    "sm",
    "smPercent",
    "bmr",
    "bone",
    "boneMass",
    "muscleMass",
    "moisturePercent",
    "musclePercent",
    "proteinPercent",
    "physicalAge",
    "bodyScore",
    "bodyType",
    # 확장 알고리즘 키
    "bfr",
    "subcutfat",
    "vfal",
    "water",
    "protein",
    "whr",
    "mineral",
)
