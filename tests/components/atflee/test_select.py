"""Active-user selection via the registered HA service."""

from .conftest import ADDRESS
from .test_platforms import entity


async def test_active_user_select_action(hass, loaded_entry):
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
