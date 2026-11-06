"""UI configuration and reauthentication for each plant/object combination."""

from datetime import datetime
import hashlib
import json

import requests
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .client import AuthenticationError, EParkaiClient
from .const import CONF_ADDRESS, CONF_INTERVAL, CONF_PLANT_ID, DOMAIN
from .production import ParseError, TZ


def config_identity(data):
    """Include exact object value so objects sharing a plant never collide."""
    identity = [data["client_id"], data[CONF_PLANT_ID], data.get(CONF_ADDRESS, "")]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()


def schema(reauth=False):
    fields = {
        vol.Required("username"): str,
        vol.Required("password"): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
    }
    if not reauth:
        fields.update({
            vol.Required("name", default="eParkai Solar"): str,
            vol.Required("client_id"): vol.All(str, vol.Match(r"^[0-9]+$")),
            vol.Required(CONF_PLANT_ID): str,
            vol.Optional(CONF_ADDRESS, default=""): str,
            vol.Required(CONF_INTERVAL, default=60): vol.In([15, 30, 60]),
        })
    return vol.Schema(fields)


class EParkaiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

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
        if user_input is not None:
            await self.async_set_unique_id(config_identity(user_input))
            self._abort_if_unique_id_configured()
            try:
                await self._validate(user_input)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except requests.RequestException:
                errors["base"] = "cannot_connect"
            except ParseError:
                errors["base"] = "invalid_response"
            else:
                return self.async_create_entry(title=user_input["name"], data=user_input)
        return self.async_show_form(step_id="user", data_schema=schema(), errors=errors)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = {**entry.data, **user_input}
            try:
                await self._validate(data)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except requests.RequestException:
                errors["base"] = "cannot_connect"
            except ParseError:
                errors["base"] = "invalid_response"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(step_id="reauth_confirm", data_schema=schema(True), errors=errors)
