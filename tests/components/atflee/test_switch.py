"""Body-composition switch via the registered HA service."""

from .conftest import ADDRESS
from .test_platforms import entity


async def test_body_composition_switch_action(hass, loaded_entry):
    switch = entity(hass, f"{ADDRESS}_enable_body_composition", "switch")
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": switch}, blocking=True
    )
    await hass.async_block_till_done()
    assert loaded_entry.options["enable_body_composition"] is True
    assert hass.states.get(switch).state == "on"
