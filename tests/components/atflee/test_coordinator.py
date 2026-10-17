"""Advertisement-driven sessions, recovery and privacy with real HA."""

import asyncio
import logging

from .test_platforms import entity
from .conftest import ADDRESS


async def test_failed_session_retries_and_keeps_link_until_unload(
    hass, loaded_entry, transport, advertisement
):
    coordinator = loaded_entry.runtime_data
    # Finish the first awake period, then exercise a connection failure on wake.
    await coordinator.async_stop()
    await coordinator.async_start()
    coordinator._handled_current_presence = False
    coordinator._last_session_end_monotonic = 0
    transport.fail_connect = True
    coordinator._async_watchdog()
    await coordinator._session_task
    assert coordinator.session_reports.failures == 1
    assert not coordinator._handled_current_presence
    assert not transport.is_connected
    assert coordinator.data.connected is False
    transport.fail_connect = False
    coordinator._last_session_end_monotonic = 0
    coordinator._async_watchdog()
    for _ in range(15):
        if transport.callbacks:
            break
        await asyncio.sleep(0)
    assert transport.is_connected
    assert coordinator.data.connected
    # Another watchdog tick must keep the same session and connection slot.
    current = coordinator._session_task
    connections = transport.connections
    coordinator._async_watchdog()
    assert coordinator._session_task is current
    assert transport.connections == connections
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    assert not transport.is_connected
    assert coordinator._session_task.done()


async def test_attribution_logs_hide_profile_but_user_values_remain(
    hass, loaded_entry, caplog
):
    coordinator = loaded_entry.runtime_data
    caplog.set_level(logging.DEBUG, logger="custom_components.atflee")
    attribution = coordinator._attribute_session(60.0, True)
    assert attribution.user_id == "user_one"
    assert "measurement attributed" in caplog.text
    assert "Test One" not in caplog.text
    assert "60.0" not in caplog.text
    assert ADDRESS not in caplog.text
    assert (
        hass.states.get(entity(hass, f"{ADDRESS}_user_one_profile_height")).state
        == "170"
    )
