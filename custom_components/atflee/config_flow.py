"""Config flow for Atflee integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_HEIGHT_CM,
    CONF_NOTIFY_TIMEOUT_SECONDS,
    CONF_BIRTH_YEAR,
    CONF_SEX,
    DEFAULT_HEIGHT_CM,
    DEFAULT_NOTIFY_TIMEOUT_SECONDS,
    DEFAULT_BIRTH_YEAR,
    DEFAULT_SEX,
    DOMAIN,
    GATT_PROFILES,
    MAX_HEIGHT_CM,
    MIN_HEIGHT_CM,
    MIN_BIRTH_YEAR,
    MAX_BIRTH_YEAR,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class Discovery:
    """Discovered Bluetooth device."""

    name: str
    info: BluetoothServiceInfoBleak


BASE_SCHEMA = {
    vol.Required(CONF_HEIGHT_CM, default=DEFAULT_HEIGHT_CM): NumberSelector(
        NumberSelectorConfig(
            min=MIN_HEIGHT_CM,
            max=MAX_HEIGHT_CM,
            step=1,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement="cm",
        )
    ),
    vol.Required(CONF_BIRTH_YEAR, default=DEFAULT_BIRTH_YEAR): NumberSelector(
        NumberSelectorConfig(
            min=MIN_BIRTH_YEAR,
            max=MAX_BIRTH_YEAR,
            step=1,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement="year",
        )
    ),
    vol.Required(CONF_SEX, default=DEFAULT_SEX): SelectSelector(
        SelectSelectorConfig(
            options=["male", "female"],
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="sex",
        )
    ),
    vol.Required(
        CONF_NOTIFY_TIMEOUT_SECONDS, default=DEFAULT_NOTIFY_TIMEOUT_SECONDS
    ): NumberSelector(
        NumberSelectorConfig(
            min=3,
            max=60,
            step=1,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement="seconds",
        )
    ),
}


class AtfleeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Atflee."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_devices: dict[str, Discovery] = {}

    def _is_atflee_candidate(self, discovery_info: BluetoothServiceInfoBleak) -> bool:
        """Check whether discovered device matches Atflee heuristics."""
        known_services = {service for service, _, _ in GATT_PROFILES}
        advertised_services = {uuid.lower() for uuid in (discovery_info.service_uuids or [])}
        if advertised_services & known_services:
            return True

        local_name = (
            discovery_info.name
            or discovery_info.advertisement.local_name
            or ""
        ).lower()
        return any(
            keyword in local_name
            for keyword in ("atflee", "앳플리", "yologram", "igripx", "jc780")
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery from HA."""
        address = discovery_info.address
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {
            "name": discovery_info.name or address,
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm bluetooth discovery."""
        if user_input is not None:
            address = self.unique_id
            assert address is not None
            return self.async_create_entry(
                title=self.context["title_placeholders"]["name"],
                data={CONF_ADDRESS: address} | user_input,
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(BASE_SCHEMA),
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual setup step."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            selected = self._discovered_devices[address]
            return self.async_create_entry(
                title=selected.name,
                data=user_input,
            )

        current_ids = self._async_current_ids()
        for service_info in async_discovered_service_info(self.hass):
            address = service_info.address
            if address in current_ids or address in self._discovered_devices:
                continue
            if service_info.name is None and service_info.advertisement.local_name is None:
                continue
            if not self._is_atflee_candidate(service_info):
                continue

            name = service_info.name or service_info.advertisement.local_name or address
            self._discovered_devices[address] = Discovery(name=name, info=service_info)

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        options = {
            address: f"{device.name} ({address})"
            for address, device in self._discovered_devices.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(options)} | BASE_SCHEMA),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowWithReload:
        """Return the options flow."""
        return AtfleeOptionsFlow(config_entry)


class AtfleeOptionsFlow(OptionsFlowWithReload):
    """Atflee options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        suggested_values = {**self._config_entry.data, **self._config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(BASE_SCHEMA), suggested_values
            ),
        )
