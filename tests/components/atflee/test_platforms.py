"""Actions, pushed data and user isolation using real HA platforms."""

import asyncio
import logging

from homeassistant.helpers import entity_registry as er

from custom_components.atflee.atflee_ble.models import AtfleeMeasurement

from .conftest import ADDRESS


def entity(hass, unique_id, domain="sensor"):
    return er.async_get(hass).async_get_entity_id(domain, "atflee", unique_id)


async def test_switch_and_select_actions(hass, loaded_entry):
    switch = entity(hass, f"{ADDRESS}_enable_body_composition", "switch")
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": switch}, blocking=True
    )
    await hass.async_block_till_done()
    assert loaded_entry.options["enable_body_composition"] is True
    assert hass.states.get(switch).state == "on"
    select = entity(hass, f"{ADDRESS}_active_user", "select")
    state = hass.states.get(select)
    label = state.attributes["options"][1]
    await hass.services.async_call(
        "select", "select_option", {"entity_id": select, "option": label}, blocking=True
    )
    assert loaded_entry.runtime_data.active_user_id == "user_one"
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": select, "option": "auto"},
        blocking=True,
    )
    assert loaded_entry.runtime_data.active_user_id is None


async def test_user_push_isolation_dynamic_entities_and_status(hass, loaded_entry):
    coordinator = loaded_entry.runtime_data
    one = entity(hass, f"{ADDRESS}_user_one_weight")
    two = entity(hass, f"{ADDRESS}_user_two_weight")
    assert hass.states.get(one).state == "unknown"
    assert hass.states.get(two).state == "unknown"
    measurement = AtfleeMeasurement(
        weight_kg=60, body_fat_pct=20, measure_status=1, is_stable=True
    )
    coordinator.async_set_updated_data(
        coordinator._build_state(
            measurement=measurement, user_id="user_one", connected=True, measuring=True
        )
    )
    await hass.async_block_till_done()
    assert float(hass.states.get(one).state) == 60
    assert hass.states.get(two).state == "unknown"
    fat = entity(hass, f"{ADDRESS}_user_one_body_fat")
    assert float(hass.states.get(fat).state) == 20
    status = entity(hass, f"{ADDRESS}_measure_status")
    assert hass.states.get(status).state == "weighing"
    coordinator.async_set_updated_data(
        coordinator._build_state(
            measurement=AtfleeMeasurement(weight_kg=80, measure_status=99),
            user_id="user_two",
            connected=False,
            measuring=False,
        )
    )
    await hass.async_block_till_done()
    assert float(hass.states.get(one).state) == 60
    assert float(hass.states.get(two).state) == 80
    assert hass.states.get(status).state == "other"
    assert hass.states.get(status).attributes["raw"] == 99


async def test_real_bluetooth_session_notification_and_unload(
    hass, loaded_entry, transport, advertisement, caplog
):
    coordinator = loaded_entry.runtime_data
    caplog.set_level(logging.DEBUG, logger="custom_components.atflee")
    # An actual HA Bluetooth manager advertisement starts the real protocol client.
    await hass.async_block_till_done()
    for _ in range(15):
        if transport.callbacks:
            break
        await asyncio.sleep(0)
    assert transport.is_connected
    assert transport.connections == 1
    frame = bytes.fromhex("010700a201190117740000000000000000000008")
    transport.push(frame)
    for _ in range(15):
        if coordinator.data.latest:
            break
        await asyncio.sleep(0)
    assert coordinator.data.latest is not None
    assert coordinator.data.latest.measure_status == 1
    assert coordinator.data.connected
    integration_logs = "\n".join(
        r.getMessage()
        for r in caplog.records
        if r.name.startswith("custom_components.atflee")
    )
    assert frame.hex() not in integration_logs
    assert "Test One" not in integration_logs
    assert ADDRESS not in integration_logs
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    assert coordinator._session_task.done()
    assert not transport.is_connected
    assert not transport.callbacks


async def test_weights_persist_and_removed_with_entry(hass, loaded_entry):
    coordinator = loaded_entry.runtime_data
    coordinator._remember_weight("user_one", 61.2, "selected")
    assert await hass.config_entries.async_reload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.runtime_data._last_weights == {"user_one": 61.2}
    await hass.config_entries.async_remove(loaded_entry.entry_id)
    assert await coordinator._store.async_load() is None
