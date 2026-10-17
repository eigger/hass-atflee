"""Device registry calls that differ between Home Assistant versions.

Home Assistant 2026.8 added ``via_device_id`` and the per config entry device
lookups, and deprecated ``via_device`` and ``async_get_device`` (both stop
working in 2027.8). Older cores only have the deprecated forms, so pick the
call by feature instead of by version. Kept free of Home Assistant imports so
it can be tested on its own.
"""

from __future__ import annotations

from typing import Any


def supports_via_device_id(device_info_cls: type) -> bool:
    """Return whether this core's DeviceInfo accepts a via device registry id."""
    return "via_device_id" in getattr(device_info_cls, "__optional_keys__", ())


def via_device_fields(
    device_info_cls: type, identifier: tuple[str, str], device_id: str | None
) -> dict[str, Any]:
    """Return the DeviceInfo fields that attach a device to its parent.

    The parent's registry id is used where the core supports it; otherwise (or
    before the parent is registered) fall back to its identifier.
    """
    if device_id and supports_via_device_id(device_info_cls):
        return {"via_device_id": device_id}
    return {"via_device": identifier}


def find_device(registry: Any, identifier: tuple[str, str], config_entry_id: str) -> Any:
    """Return the device of this config entry with the given identifier."""
    lookup = getattr(registry, "async_get_device_by_identifier", None)
    if lookup is not None:
        return lookup(identifier, config_entry_id)
    return registry.async_get_device(identifiers={identifier})
