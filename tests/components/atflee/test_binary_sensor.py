"""Connectivity is published by the actual HA binary-sensor platform."""

from .conftest import ADDRESS
from .test_platforms import entity


async def test_connection_state_tracks_session(hass, loaded_entry):
    coordinator = loaded_entry.runtime_data
    entity_id = entity(hass, f"{ADDRESS}_ble_connection", "binary_sensor")
    assert hass.states.get(entity_id).state == "off"
    coordinator.async_set_updated_data(
        coordinator._build_state(connected=True, measuring=False)
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"
    coordinator.async_set_updated_data(
        coordinator._build_state(connected=False, measuring=False)
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "off"
