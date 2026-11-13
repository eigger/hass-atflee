"""Protocol client connection faults at the external GATT boundary."""

import asyncio

import pytest
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from blesession import SessionDropped, SessionTrace, WriteTimeout

from custom_components.atflee.atflee_ble.connection import AtfleeBleClient
from custom_components.atflee.const import GATT_PROFILES

from .conftest import ADDRESS


@pytest.mark.parametrize("failure", [TimeoutError, asyncio.CancelledError])
async def test_notify_failure_releases_open_link(hass, transport, failure, monkeypatch):
    async def fail(*args):
        raise failure()

    monkeypatch.setattr(transport, "start_notify", fail)
    client = AtfleeBleClient(hass, ADDRESS)
    with pytest.raises(failure):
        await client.connect_with_profiles(
            BLEDevice(ADDRESS, "Test", {}), GATT_PROFILES[:1]
        )
    assert not transport.is_connected
    assert transport.disconnects == 1
    assert not client.is_connected


async def test_full_session_collects_route_mtu_and_own_close_is_not_a_drop(
    hass, transport
):
    trace = SessionTrace()
    transport._connected_scanner = "test-proxy"
    client = AtfleeBleClient(hass, ADDRESS)
    await client.connect_with_profiles(
        BLEDevice(ADDRESS, "Test", {"source": "advertised-proxy"}),
        GATT_PROFILES[:1],
        trace=trace,
    )
    assert trace.stage == "session"
    assert trace.link.via == "test-proxy"
    assert trace.link.source == "advertised-proxy"
    assert "mtu" not in trace.facts
    await client.disconnect()
    assert trace.stage is None
    assert trace.facts["mtu"] == 247
    assert "link_dropped" not in trace.facts
    assert {"connect", "session", "disconnect"} <= trace.timings.keys()


async def test_profile_recovery_does_not_leave_a_failed_stage(
    hass, transport, monkeypatch
):
    trace = SessionTrace()
    original = transport.start_notify
    attempts = 0

    async def first_profile_fails(*args):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise BleakError("profile unavailable")
        await original(*args)

    monkeypatch.setattr(transport, "start_notify", first_profile_fails)
    client = AtfleeBleClient(hass, ADDRESS)
    selected = await client.connect_with_profiles(
        BLEDevice(ADDRESS, "Test", {}),
        GATT_PROFILES[:2],
        trace=trace,
    )
    assert selected == GATT_PROFILES[1]
    assert transport.connections == 2 and transport.disconnects == 1
    assert trace.failed_primary is None
    await client.disconnect()
    assert trace.stage is None and trace.failed_primary is None


async def test_profile_recovery_discards_abandoned_link_facts(
    hass, transport, monkeypatch
):
    trace = SessionTrace()
    trace.note(caller_fact=42)
    transport.mtu_size = 99
    transport._connected_scanner = "failed-proxy"
    original_notify = transport.start_notify
    original_disconnect = transport.disconnect
    notify_calls = 0
    disconnect_calls = 0

    async def notify(*args):
        nonlocal notify_calls
        notify_calls += 1
        if notify_calls == 1:
            transport.drop()
            raise BleakError("first profile disconnected")
        await original_notify(*args)

    async def disconnect():
        nonlocal disconnect_calls
        disconnect_calls += 1
        if disconnect_calls == 1:
            transport.mtu_size = 247
            transport._connected_scanner = "selected-proxy"
            raise BleakError("abandoned link cleanup failed")
        await original_disconnect()

    monkeypatch.setattr(transport, "start_notify", notify)
    monkeypatch.setattr(transport, "disconnect", disconnect)
    client = AtfleeBleClient(hass, ADDRESS)
    await client.connect_with_profiles(
        BLEDevice(ADDRESS, "Test", {}), GATT_PROFILES[:2], trace=trace
    )
    assert trace.link.via == "selected-proxy"
    assert trace.facts == {"caller_fact": 42}
    assert trace.failed_primary is None
    await client.disconnect()
    assert trace.facts == {"caller_fact": 42, "mtu": 247}
    assert {"connect", "session", "disconnect"} <= trace.timings.keys()


async def test_link_drop_wakes_packet_wait_and_is_recorded(hass, transport):
    trace = SessionTrace()
    client = AtfleeBleClient(hass, ADDRESS)
    await client.connect_with_profiles(
        BLEDevice(ADDRESS, "Test", {}),
        GATT_PROFILES[:1],
        trace=trace,
    )
    waiting = asyncio.create_task(client.wait_for_measurement(30))
    await asyncio.sleep(0)
    transport.drop()
    with pytest.raises(SessionDropped):
        await asyncio.wait_for(waiting, 1)
    await client.disconnect()
    assert transport.disconnects == 1  # release the proxy slot even on a dead link
    assert trace.facts["link_dropped"] is True
    assert trace.facts["dropped_after_s"] >= 0


async def test_final_queued_packet_is_delivered_before_drop(hass, transport):
    client = AtfleeBleClient(hass, ADDRESS)
    await client.connect_with_profiles(
        BLEDevice(ADDRESS, "Test", {}), GATT_PROFILES[:1]
    )
    transport.push(bytes.fromhex("010700a201190117740000000000000000000008"))
    transport.drop()
    measurement = await client.wait_for_measurement(30)
    assert measurement.weight_kg is not None
    with pytest.raises(SessionDropped):
        await client.wait_for_measurement(30)
    await client.disconnect()


async def test_write_timeout_does_not_retry_another_mode(hass, transport, monkeypatch):
    calls = []

    async def stuck(uuid, data, response=False):
        calls.append(response)
        await asyncio.Event().wait()

    monkeypatch.setattr(transport, "write_gatt_char", stuck)
    monkeypatch.setattr(
        "custom_components.atflee.atflee_ble.connection.WRITE_TIMEOUT_SECONDS", 0.01
    )
    client = AtfleeBleClient(hass, ADDRESS)
    await client.connect_with_profiles(
        BLEDevice(ADDRESS, "Test", {}), GATT_PROFILES[:1]
    )
    with pytest.raises(WriteTimeout):
        await asyncio.wait_for(client.send_frames([b"frame"]), 1)
    assert calls == [True]
    await client.disconnect()


@pytest.mark.parametrize("unsupported", [True, False])
async def test_response_mode_fallback_does_not_retry_transport_faults(
    hass, transport, monkeypatch, unsupported
):
    calls = []

    async def write(uuid, data, response=False):
        calls.append(response)
        if response:
            raise BleakError(
                "Write not permitted" if unsupported else "transport failed"
            )

    monkeypatch.setattr(transport, "write_gatt_char", write)
    client = AtfleeBleClient(hass, ADDRESS)
    await client.connect_with_profiles(
        BLEDevice(ADDRESS, "Test", {}), GATT_PROFILES[:1]
    )
    if unsupported:
        assert await client.send_frames([b"frame"])
        assert calls == [True, False]
    else:
        with pytest.raises(BleakError, match="transport failed"):
            await client.send_frames([b"frame"])
        assert calls == [True]
    await client.disconnect()


async def test_cancelled_packet_wait_does_not_steal_the_next_packet(hass, transport):
    client = AtfleeBleClient(hass, ADDRESS)
    await client.connect_with_profiles(
        BLEDevice(ADDRESS, "Test", {}), GATT_PROFILES[:1]
    )
    waiting = asyncio.create_task(client.wait_for_measurement(30))
    await asyncio.sleep(0)
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting
    transport.push(bytes.fromhex("010700a201190117740000000000000000000008"))
    measurement = await asyncio.wait_for(client.wait_for_measurement(30), 1)
    assert measurement.weight_kg is not None
    await client.disconnect()


async def test_failed_profile_disconnect_is_bounded(hass, transport, monkeypatch):
    async def fail(*args):
        raise ValueError("notify failed")

    async def stuck():
        await asyncio.Event().wait()

    monkeypatch.setattr(transport, "start_notify", fail)
    monkeypatch.setattr(transport, "disconnect", stuck)
    monkeypatch.setattr(
        "custom_components.atflee.atflee_ble.connection.DISCONNECT_TIMEOUT_SECONDS",
        0.01,
    )
    client = AtfleeBleClient(hass, ADDRESS)
    with pytest.raises(ValueError, match="notify failed"):
        await asyncio.wait_for(
            client.connect_with_profiles(
                BLEDevice(ADDRESS, "Test", {}), GATT_PROFILES[:1]
            ),
            1,
        )
    assert not client.is_connected


async def test_reconnect_after_notify_failure(hass, transport, monkeypatch):
    original = transport.start_notify

    async def fail(*args):
        raise ValueError("notify failed")

    monkeypatch.setattr(transport, "start_notify", fail)
    client = AtfleeBleClient(hass, ADDRESS)
    with pytest.raises(ValueError):
        await client.connect_with_profiles(
            BLEDevice(ADDRESS, "Test", {}), GATT_PROFILES[:1]
        )
    monkeypatch.setattr(transport, "start_notify", original)
    await client.connect_with_profiles(
        BLEDevice(ADDRESS, "Test", {}), GATT_PROFILES[:1]
    )
    assert client.is_connected
    await client.disconnect()
    assert not transport.is_connected
    assert not transport.callbacks


async def test_transport_error_log_does_not_expose_device_or_profile(
    hass, transport, monkeypatch, caplog
):
    import logging

    caplog.set_level(logging.DEBUG, logger="custom_components.atflee")

    async def fail(*args):
        raise ValueError(f"{ADDRESS} Example Sensitive 60.123")

    monkeypatch.setattr(transport, "start_notify", fail)
    client = AtfleeBleClient(hass, ADDRESS)
    with pytest.raises(ValueError):
        await client.connect_with_profiles(
            BLEDevice(ADDRESS, "Test", {}), GATT_PROFILES[:1]
        )
    logs = "\n".join(
        r.getMessage()
        for r in caplog.records
        if r.name.startswith("custom_components.atflee")
    )
    assert "ValueError" in logs
    assert ADDRESS not in logs
    assert "Example Sensitive" not in logs
    assert "60.123" not in logs


async def test_service_change_swaps_profile_and_refreshes_optional_notify(
    hass, transport
):
    """A new GATT map must replace the prior session's UUIDs and listeners."""
    from types import SimpleNamespace

    from custom_components.atflee.const import OPTIONAL_NOTIFY_UUIDS

    service_uuid, notify_uuid, write_uuid = GATT_PROFILES[0]
    optional_uuid = OPTIONAL_NOTIFY_UUIDS[0]

    class ChangedServices:
        def __init__(self, swapped, optional_supported):
            self.characteristics = {
                notify_uuid: SimpleNamespace(
                    uuid=notify_uuid, properties=["write"] if swapped else ["notify"]
                ),
                write_uuid: SimpleNamespace(
                    uuid=write_uuid, properties=["notify"] if swapped else ["write"]
                ),
                optional_uuid: SimpleNamespace(
                    uuid=optional_uuid,
                    properties=["notify"] if optional_supported else ["write"],
                ),
            }
            self.services = {
                service_uuid: SimpleNamespace(
                    uuid=service_uuid,
                    characteristics=list(self.characteristics.values()),
                )
            }

        def __iter__(self):
            return iter(self.services.values())

        def get_characteristic(self, uuid):
            return self.characteristics.get(uuid)

    transport.services = ChangedServices(swapped=True, optional_supported=True)
    client = AtfleeBleClient(hass, ADDRESS)
    selected = await client.connect_with_profiles(
        BLEDevice(ADDRESS, "Test", {}), GATT_PROFILES[:1]
    )
    assert selected == (service_uuid, write_uuid, notify_uuid)
    assert set(transport.callbacks) == {write_uuid, optional_uuid}
    assert await client.send_frames([b"example"])
    assert transport.writes[-1] == (notify_uuid, b"example", True)

    # A reconnect after the peripheral's service map changes must drop both old
    # subscriptions before selecting the new map; optional write-only UUIDs are
    # not usable notification channels.
    transport.services = ChangedServices(swapped=False, optional_supported=False)
    selected = await client.connect_with_profiles(
        BLEDevice(ADDRESS, "Test", {}), GATT_PROFILES[:1]
    )
    assert selected == GATT_PROFILES[0]
    assert set(transport.callbacks) == {notify_uuid}
    assert client._extra_notify_char_uuids == []
    assert await client.send_frames([b"next"])
    assert transport.writes[-1] == (write_uuid, b"next", True)
    assert transport.connections == 2
    assert transport.disconnects == 1
    await client.disconnect()
    assert transport.disconnects == 2
    assert not transport.callbacks
    assert not client.is_connected
