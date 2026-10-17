"""Protocol client connection faults at the external GATT boundary."""

import asyncio

import pytest
from bleak.backends.device import BLEDevice

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
