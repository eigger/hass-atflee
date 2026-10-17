"""Actual config-entry, platform and cleanup lifecycle."""

import asyncio

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.atflee.coordinator import AtfleeDataUpdateCoordinator

from .conftest import ADDRESS


def entities(hass, entry, domain=None):
    return [
        e
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if domain is None or e.domain == domain
    ]


async def test_setup_platforms_registry_and_unload(hass, loaded_entry, transport):
    entry = loaded_entry
    assert entry.state is ConfigEntryState.LOADED
    assert {e.domain for e in entities(hass, entry)} == {
        "sensor",
        "binary_sensor",
        "switch",
        "select",
    }
    registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(devices) == 3
    parent = next(d for d in devices if ("atflee", ADDRESS) in d.identifiers)
    assert all(d.via_device_id == parent.id for d in devices if d.id != parent.id)
    coordinator = entry.runtime_data
    assert coordinator._adv_unsub is not None
    assert coordinator._watchdog_unsub is not None
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert coordinator._adv_unsub is None
    assert coordinator._watchdog_unsub is None
    assert not transport.is_connected


@pytest.mark.parametrize("cancel", [False, True])
async def test_partial_start_cleanup(hass, entry, bluetooth_ready, monkeypatch, cancel):
    original = AtfleeDataUpdateCoordinator.async_start
    seen = []

    async def fail(self):
        seen.append(self)
        await original(self)
        if cancel:
            raise asyncio.CancelledError
        raise RuntimeError("startup interrupted")

    monkeypatch.setattr(AtfleeDataUpdateCoordinator, "async_start", fail)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert seen[0]._adv_unsub is None
    assert seen[0]._watchdog_unsub is None


async def test_failed_first_refresh_releases_callbacks(
    hass, entry, bluetooth_ready, monkeypatch
):
    from homeassistant.helpers.update_coordinator import UpdateFailed

    seen = []

    async def fail(self):
        seen.append(self)
        raise UpdateFailed("initial refresh failed")

    monkeypatch.setattr(AtfleeDataUpdateCoordinator, "_async_update_data", fail)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert seen[0]._adv_unsub is None
    assert seen[0]._watchdog_unsub is None


async def test_partial_forward_failure_cleans_entities(
    hass, entry, bluetooth_ready, monkeypatch
):
    original = hass.config_entries.async_forward_entry_setups

    async def fail(config, platforms):
        await original(config, platforms)
        raise RuntimeError("platform forwarding failed")

    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", fail)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data._adv_unsub is None
    assert entry.runtime_data._watchdog_unsub is None
    assert all(
        s.state == "unavailable"
        for s in hass.states.async_all()
        if s.entity_id.startswith("sensor.test_one")
    )


async def test_existing_v1_entry_without_users(hass, bluetooth_ready, transport):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    legacy = MockConfigEntry(
        domain="atflee",
        version=1,
        title="Existing scale",
        data={
            "address": "11:22:33:44:55:66",
            "notify_timeout_seconds": 12,
            "enable_body_composition": False,
        },
    )
    legacy.add_to_hass(hass)
    assert await hass.config_entries.async_setup(legacy.entry_id)
    await hass.async_block_till_done()
    assert legacy.version == 1
    assert legacy.subentries == {}
    assert legacy.runtime_data.user_subentries() == {}
    assert await hass.config_entries.async_unload(legacy.entry_id)
