"""Exercise actual HA APIs; only portal I/O and platform forwarding are mocked."""

from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile
from types import MappingProxyType
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
import requests
from probatio import to_field_list

from custom_components.eparkai_insights import async_setup_entry, async_unload_entry
from custom_components.eparkai_insights.client import AuthenticationError, EParkaiClient
from custom_components.eparkai_insights.config_flow import EParkaiConfigFlow, EParkaiOptionsFlow, config_identity
from custom_components.eparkai_insights.const import DOMAIN
from custom_components.eparkai_insights.coordinator import EParkaiCoordinator
from custom_components.eparkai_insights.production import ParseError, TZ, expected_intervals
from custom_components.eparkai_insights.sensor import EParkaiSensor

DATA = {
    "name": "Test solar", "username": "synthetic", "password": "not-a-real-password",
    "client_id": "123", "power_plant_id": "456", "object_address": "Synthetic object",
    "interval_minutes": 60,
}


class HomeAssistantRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.hass = HomeAssistant(self.directory.name)
        self.hass.config_entries = ConfigEntries(self.hass, {})
        await self.hass.config_entries.async_initialize()
        self.entry = ConfigEntry(
            version=1, minor_version=1, domain=DOMAIN, title="Test solar",
            data=DATA, options={}, source="user", unique_id=config_identity(DATA),
            discovery_keys=MappingProxyType({}), subentries_data=[],
            state=ConfigEntryState.SETUP_IN_PROGRESS,
        )
        yesterday = datetime.now(TZ).date() - timedelta(days=1)
        self.intervals = [(stamp.replace(tzinfo=None), 1.0, stamp.isoformat())
                          for stamp in expected_intervals(yesterday, 60)]
        self.coordinators = []

    async def asyncTearDown(self):
        for coordinator in self.coordinators:
            await coordinator.async_shutdown()
            coordinator.client.close()
        await self.hass.async_stop(force=True)
        self.directory.cleanup()

    def flow(self):
        flow = EParkaiConfigFlow()
        flow.hass = self.hass
        flow.context = {"source": "user"}
        flow.handler = DOMAIN
        return flow

    def coordinator(self):
        coordinator = EParkaiCoordinator(self.hass, self.entry)
        self.coordinators.append(coordinator)
        return coordinator

    async def test_ui_form_is_serializable_and_creates_entry(self):
        flow = self.flow()
        form = await flow.async_step_user()
        self.assertEqual(form["type"], FlowResultType.FORM)
        from homeassistant.helpers.config_validation import custom_serializer
        serialized = to_field_list(form["data_schema"], custom_serializer=custom_serializer)
        self.assertTrue(any(item["name"] == "password" for item in serialized))
        with patch.object(EParkaiClient, "fetch", return_value=self.intervals):
            result = await flow.async_step_user(dict(DATA))
        self.assertEqual(result["type"], FlowResultType.CREATE_ENTRY)
        self.assertEqual(result["data"], DATA)

    async def test_ui_reports_auth_and_connection_errors(self):
        for error, key in ((AuthenticationError(), "invalid_auth"), (requests.Timeout(), "cannot_connect")):
            with self.subTest(key=key):
                flow = self.flow()
                with patch.object(EParkaiClient, "fetch", side_effect=error):
                    result = await flow.async_step_user(dict(DATA))
                self.assertEqual(result["errors"], {"base": key})

    async def test_parser_error_exposes_safe_reason(self):
        flow = self.flow()
        with patch.object(EParkaiClient, "fetch", side_effect=ParseError("Invalid generation JSON")):
            result = await flow.async_step_user(dict(DATA))
        self.assertEqual(result["errors"], {"base": "invalid_response"})
        self.assertEqual(result["description_placeholders"]["reason"], "Invalid generation JSON")

    async def test_real_coordinator_storage_and_sensor_metadata(self):
        coordinator = self.coordinator()
        await coordinator.async_load()
        with patch.object(EParkaiClient, "fetch", return_value=self.intervals):
            await coordinator.async_config_entry_first_refresh()
        daily = EParkaiSensor(coordinator, "daily")
        hourly = EParkaiSensor(coordinator, "hourly")
        self.assertEqual(daily.native_value, len(self.intervals))
        self.assertEqual(hourly.native_value, 1)
        self.assertEqual(daily.native_unit_of_measurement, "kWh")
        self.assertIsNone(daily.state_class)
        self.assertEqual(daily.icon, "mdi:solar-power")
        self.assertEqual(daily.device_info["identifiers"], {(DOMAIN, self.entry.unique_id)})
        self.assertIn("date", daily.extra_state_attributes)
        restored = self.coordinator()
        await restored.async_load()
        self.assertEqual(restored.snapshot, coordinator.snapshot)

    async def test_setup_and_unload_use_current_platform_api(self):
        with patch.object(EParkaiClient, "fetch", return_value=self.intervals), patch.object(
            self.hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
        ) as forward:
            self.assertTrue(await async_setup_entry(self.hass, self.entry))
            forward.assert_awaited_once()
        self.coordinators.append(self.entry.runtime_data)
        with patch.object(self.hass.config_entries, "async_unload_platforms", new_callable=AsyncMock, return_value=True):
            self.assertTrue(await async_unload_entry(self.hass, self.entry))

    async def test_auth_failure_uses_home_assistant_exception(self):
        coordinator = self.coordinator()
        with patch.object(EParkaiClient, "fetch", side_effect=AuthenticationError):
            with self.assertRaises(ConfigEntryAuthFailed):
                await coordinator._async_update_data()

    async def test_network_failure_keeps_cached_sensor_reading(self):
        coordinator = self.coordinator()
        with patch.object(EParkaiClient, "fetch", return_value=self.intervals):
            await coordinator.async_config_entry_first_refresh()
        before = dict(coordinator.snapshot)
        with patch.object(EParkaiClient, "fetch", side_effect=requests.Timeout):
            with self.assertRaises(UpdateFailed):
                await coordinator._async_update_data()
        self.assertEqual(coordinator.snapshot, before)
        self.assertTrue(EParkaiSensor(coordinator, "daily").available)

    async def test_options_flow_connects_without_copying_statistic_ids(self):
        coordinator = self.coordinator()
        self.entry.runtime_data = coordinator
        flow = EParkaiOptionsFlow()
        flow.hass = self.hass
        flow.handler = self.entry.entry_id
        with patch.object(self.hass.config_entries, "async_get_known_entry", return_value=self.entry):
            form = await flow.async_step_init()
            from homeassistant.helpers.config_validation import custom_serializer
            fields = to_field_list(form["data_schema"], custom_serializer=custom_serializer)
            self.assertEqual([field["name"] for field in fields], ["energy_mode"])
            with patch.object(coordinator, "async_request_refresh", new_callable=AsyncMock), patch(
                "custom_components.eparkai_insights.energy.async_connect_energy", new_callable=AsyncMock
            ) as connect:
                result = await flow.async_step_init({"energy_mode": "remote"})
                self.assertEqual(result["errors"], {"base": "import_not_ready"})
                connect.assert_not_awaited()
                coordinator.snapshot["statistics_import_status"] = "imported"
                coordinator.last_update_success = True
                result = await flow.async_step_init({"energy_mode": "remote"})
                self.assertEqual(result["type"], FlowResultType.CREATE_ENTRY)
                connect.assert_awaited_once_with(self.hass, self.entry, "remote")
