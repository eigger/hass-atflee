"""Config and subentry flows through Home Assistant's actual flow managers."""

from homeassistant import data_entry_flow
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER

from .conftest import ADDRESS

PROFILE = {
    "name": "Example",
    "height_cm": 170,
    "birth_date": "1990-01-01",
    "sex": "male",
    "expected_weight_kg": 60,
}


async def test_no_devices(hass, bluetooth_ready):
    result = await hass.config_entries.flow.async_init(
        "atflee", context={"source": SOURCE_USER}
    )
    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_discovery_confirmation_profile_and_duplicate(
    hass, advertisement, transport
):
    for progress in hass.config_entries.flow.async_progress():
        hass.config_entries.flow.async_abort(progress["flow_id"])
    result = await hass.config_entries.flow.async_init(
        "atflee", context={"source": SOURCE_BLUETOOTH}, data=advertisement
    )
    assert result["step_id"] == "bluetooth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"notify_timeout_seconds": 3, "enable_body_composition": False},
    )
    assert result["step_id"] == "first_user"
    invalid = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**PROFILE, "birth_date": "invalid"}
    )
    assert invalid["errors"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], PROFILE)
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.unique_id == ADDRESS
    assert len(entry.subentries) == 1
    sub = next(iter(entry.subentries.values()))
    assert sub.data["name"] == "Example"
    assert sub.data["slot"] == 1
    again = await hass.config_entries.flow.async_init(
        "atflee", context={"source": SOURCE_BLUETOOTH}, data=advertisement
    )
    assert again["reason"] == "already_configured"


async def test_manual_discovery(hass, advertisement, transport):
    result = await hass.config_entries.flow.async_init(
        "atflee", context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "address": ADDRESS,
            "notify_timeout_seconds": 3,
            "enable_body_composition": False,
        },
    )
    assert result["step_id"] == "first_user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], PROFILE)
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_options_live_and_reload(hass, loaded_entry):
    coordinator = loaded_entry.runtime_data
    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
    assert result["step_id"] == "init"
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "notify_timeout_seconds": 3,
            "enable_body_composition": True,
            "match_tolerance_kg": 4,
            "fallback_max_delta_kg": 15,
        },
    )
    await hass.async_block_till_done()
    assert loaded_entry.runtime_data is coordinator
    assert loaded_entry.options["enable_body_composition"] is True
    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], {**loaded_entry.options, "notify_timeout_seconds": 4}
    )
    await hass.async_block_till_done()
    assert loaded_entry.runtime_data is not coordinator
    assert coordinator._adv_unsub is None
    assert coordinator._watchdog_unsub is None


async def test_subentry_create_reconfigure_and_reload(hass, loaded_entry):
    previous = loaded_entry.runtime_data
    result = await hass.config_entries.subentries.async_init(
        (loaded_entry.entry_id, "user"), context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    invalid = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**PROFILE, "name": "Test One"}
    )
    assert invalid["errors"]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], PROFILE
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    added = next(s for s in loaded_entry.subentries.values() if s.title == "Example")
    assert added.data["slot"] == 3
    assert loaded_entry.runtime_data is not previous
    result = await hass.config_entries.subentries.async_init(
        (loaded_entry.entry_id, "user"),
        context={"source": "reconfigure", "subentry_id": added.subentry_id},
    )
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**PROFILE, "name": "Renamed"}
    )
    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    await hass.async_block_till_done()
    updated = loaded_entry.subentries[added.subentry_id]
    assert updated.data["slot"] == 3
    assert updated.data["name"] == "Renamed"
