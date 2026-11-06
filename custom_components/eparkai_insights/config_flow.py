"""UI configuration and reauthentication for each plant/object combination."""

from datetime import datetime
import hashlib
import json
import logging

import requests
import probatio
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .client import AuthenticationError, EParkaiClient
from .const import CONF_ADDRESS, CONF_INTERVAL, CONF_PLANT_ID, DOMAIN
from .production import ParseError, TZ

_LOGGER = logging.getLogger(__name__)


def config_identity(data):
    """Include exact object value so objects sharing a plant never collide."""
    identity = [data["client_id"], data[CONF_PLANT_ID], data.get(CONF_ADDRESS, "")]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()


def schema(reauth=False):
    fields = {
        probatio.Required("username"): str,
        probatio.Required("password"): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
    }
    if not reauth:
        fields.update({
            probatio.Required("name", default="eParkai įžvalgos"): str,
            probatio.Required("client_id"): probatio.All(str, probatio.Match(r"^[0-9]+$")),
            probatio.Required(CONF_PLANT_ID): str,
            probatio.Optional(CONF_ADDRESS, default=""): str,
            probatio.Required(CONF_INTERVAL, default=60): probatio.In([15, 30, 60]),
        })
    return probatio.Schema(fields)


class EParkaiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EParkaiOptionsFlow()

    async def _validate(self, data):
        client = EParkaiClient(data["username"], data["password"], data["client_id"])
        try:
            await self.hass.async_add_executor_job(
                client.fetch, data[CONF_PLANT_ID], data.get(CONF_ADDRESS, ""), datetime.now(TZ),
            )
        finally:
            await self.hass.async_add_executor_job(client.close)

    async def async_step_user(self, user_input=None):
        errors = {}
        placeholders = {"reason": ""}
        if user_input is not None:
            await self.async_set_unique_id(config_identity(user_input))
            self._abort_if_unique_id_configured()
            try:
                await self._validate(user_input)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except requests.RequestException:
                errors["base"] = "cannot_connect"
            except ParseError as err:
                errors["base"] = "invalid_response"
                # ParseError messages are fixed descriptions, never response bodies.
                placeholders["reason"] = str(err)
            else:
                return self.async_create_entry(title=user_input["name"], data=user_input)
        return self.async_show_form(step_id="user", data_schema=schema(), errors=errors,
                                    description_placeholders=placeholders)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        placeholders = {"reason": ""}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = {**entry.data, **user_input}
            try:
                await self._validate(data)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except requests.RequestException:
                errors["base"] = "cannot_connect"
            except ParseError as err:
                errors["base"] = "invalid_response"
                placeholders["reason"] = str(err)
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(step_id="reauth_confirm", data_schema=schema(True), errors=errors,
                                    description_placeholders=placeholders)


class EParkaiOptionsFlow(config_entries.OptionsFlow):
    """One UI action to import and connect the historical series to Energy."""

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            from .energy import async_connect_energy

            coordinator = self.config_entry.runtime_data
            await coordinator.async_request_refresh()
            if (not coordinator.last_update_success or
                    coordinator.snapshot.get("statistics_import_status") != "imported"):
                errors["base"] = "import_not_ready"
            else:
                try:
                    await async_connect_energy(self.hass, self.config_entry, user_input["energy_mode"])
                except Exception:
                    _LOGGER.exception("Unable to connect eParkai statistics to Energy")
                    errors["base"] = "energy_failed"
                else:
                    return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="init", errors=errors, data_schema=probatio.Schema({
            probatio.Required("energy_mode", default="remote"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=["remote", "solar", "export", "manual"],
                                              translation_key="energy_mode", mode="dropdown")),
        }))
