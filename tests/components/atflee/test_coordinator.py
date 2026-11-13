"""Advertisement-driven sessions, recovery and privacy with real HA."""

import asyncio
import logging

import pytest

from custom_components.atflee.atflee_ble.packet import CMD_WEIGHT_STABLE, build_frames

from .test_platforms import entity
from .conftest import ADDRESS


async def _connected(coordinator, transport):
    for _ in range(30):
        if transport.callbacks and coordinator.data.connected:
            return
        await asyncio.sleep(0)
    assert transport.callbacks and coordinator.data.connected


def _stable_weight(grams=60000):
    return build_frames(
        CMD_WEIGHT_STABLE, grams.to_bytes(4, "big") + b"\x00", pkg_index=7
    )[0]


async def test_premature_drop_counts_failure_and_allows_next_wake(
    hass, loaded_entry, transport, advertisement
):
    coordinator = loaded_entry.runtime_data
    await _connected(coordinator, transport)
    transport.drop()
    await asyncio.wait_for(coordinator._session_task, 1)
    report = coordinator.session_reports.last_failure
    assert report["failed_stage"] == "transfer"
    assert report["likely_cause_key"] == "link_lost"
    assert report["link_dropped"] is True
    assert report["mtu"] == 247
    assert not coordinator._handled_current_presence
    assert coordinator.session_reports.failures == 1
    assert transport.disconnects == 1
    coordinator._last_session_end_monotonic = 0
    coordinator._async_watchdog()
    await _connected(coordinator, transport)
    assert transport.connections == 2


async def test_queued_final_weight_is_published_when_peer_cannot_receive_ack(
    hass, loaded_entry, transport, advertisement
):
    coordinator = loaded_entry.runtime_data
    await _connected(coordinator, transport)
    # Notification and drop arrive in the same loop turn. The packet must not
    # disappear merely because the now-dead link cannot accept its B0 reply.
    transport.push(bytes.fromhex("000a00a1337116200019010a1900000000000018"))
    transport.push(_stable_weight())
    transport.push(_stable_weight(61000))
    transport.drop()
    await asyncio.wait_for(coordinator._session_task, 1)
    assert coordinator.data.latest.weight_kg == 61
    assert coordinator.session_reports.failures == 0
    assert coordinator.session_reports.last["success"] is True
    assert coordinator.session_reports.last["link_dropped"] is True
    assert coordinator.session_reports.last["packets"] == 3
    assert coordinator._handled_current_presence
    assert not coordinator.data.connected


async def test_ack_write_timeout_is_a_transfer_failure_not_normal_idle(
    hass, loaded_entry, transport, advertisement, monkeypatch
):
    coordinator = loaded_entry.runtime_data
    await _connected(coordinator, transport)

    async def stuck(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(transport, "write_gatt_char", stuck)
    monkeypatch.setattr(
        "custom_components.atflee.atflee_ble.connection.WRITE_TIMEOUT_SECONDS", 0.01
    )
    transport.push(_stable_weight())
    await asyncio.wait_for(coordinator._session_task, 1)
    report = coordinator.session_reports.last_failure
    assert report["failed_stage"] == "transfer"
    assert report["likely_cause_key"] == "write_timeout"
    assert coordinator.session_reports.failures == 1
    assert not coordinator._handled_current_presence


async def test_stable_weight_keeps_existing_ack_protocol(
    hass, loaded_entry, transport, advertisement
):
    coordinator = loaded_entry.runtime_data
    await _connected(coordinator, transport)
    transport.push(_stable_weight())
    for _ in range(30):
        if (
            coordinator.data.latest is not None
            and coordinator.data.latest.weight_kg == 60
        ):
            break
        await asyncio.sleep(0)
    assert coordinator.data.latest.weight_kg == 60
    _, frame, response = transport.writes[-1]
    assert frame[3] == 0xB0
    assert frame[4] == 7  # the scale's package index is echoed by its ACK
    assert response is True
    assert transport.is_connected


async def test_backend_ack_timeout_is_not_normal_idle(
    hass, loaded_entry, transport, advertisement, monkeypatch
):
    coordinator = loaded_entry.runtime_data
    await _connected(coordinator, transport)

    async def backend_timeout(*args, **kwargs):
        raise TimeoutError("backend ACK deadline")

    monkeypatch.setattr(transport, "write_gatt_char", backend_timeout)
    transport.push(_stable_weight())
    await asyncio.wait_for(coordinator._session_task, 1)
    report = coordinator.session_reports.last_failure
    assert report["success"] is False
    assert report["failed_stage"] == "transfer"
    assert report["error"] == "backend ACK deadline"
    assert coordinator.session_reports.failures == 1
    assert not coordinator._handled_current_presence


@pytest.fixture
def short_idle(monkeypatch):
    monkeypatch.setattr(
        "custom_components.atflee.coordinator.AtfleeDataUpdateCoordinator._idle_timeout_seconds",
        lambda self: 0.01,
    )


async def test_idle_without_measurement_retains_existing_normal_end_policy(
    hass, short_idle, loaded_entry, transport, advertisement
):
    coordinator = loaded_entry.runtime_data
    await asyncio.wait_for(coordinator._session_task, 1)
    assert coordinator.session_reports.last["success"] is True
    assert coordinator.session_reports.failures == 0
    assert "link_dropped" not in coordinator.session_reports.last
    assert coordinator._handled_current_presence
    assert not transport.is_connected


async def test_external_cancel_does_not_record_a_failed_measurement(
    hass, loaded_entry, transport, advertisement
):
    coordinator = loaded_entry.runtime_data
    await _connected(coordinator, transport)
    task = coordinator._session_task
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert coordinator.session_reports.last is None
    assert coordinator.session_reports.failures == 0
    assert transport.disconnects == 1
    assert not transport.callbacks


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
