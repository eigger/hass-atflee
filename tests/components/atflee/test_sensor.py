"""Real platform measurement states and per-user isolation."""

from custom_components.atflee.atflee_ble.models import AtfleeMeasurement

from .conftest import ADDRESS
from .test_platforms import entity


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
