"""Actions, pushed data and user isolation using real HA platforms."""

import asyncio
import logging

from homeassistant.helpers import entity_registry as er

from .conftest import ADDRESS


def entity(hass, unique_id, domain="sensor"):
    return er.async_get(hass).async_get_entity_id(domain, "atflee", unique_id)


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
