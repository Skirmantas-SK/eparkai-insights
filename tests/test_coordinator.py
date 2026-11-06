"""Coordinator behavior with minimal HA boundary doubles (not a HA runtime test)."""

from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import requests

from test_production import day_samples, payload
from custom_components.eparkai.client import AuthenticationError
from custom_components.eparkai.production import TZ, parse_intervals


class AuthFailed(Exception):
    pass


class UpdateFailed(Exception):
    pass


class FakeCoordinator:
    def __init__(self, hass, logger, **kwargs):
        self.hass = hass
        self.update_interval = kwargs["update_interval"]
        self.last_update_success = True


class FakeStore:
    def __init__(self, *args):
        self.saved = None

    async def async_load(self):
        return self.saved

    async def async_save(self, data):
        self.saved = data


class FakeHass:
    async def async_add_executor_job(self, fn, *args):
        return fn(*args)


def load_coordinator():
    """Keep HA doubles scoped to module loading; avoid shadowing installed HA."""
    modules = {}
    for name, attributes in {
        "homeassistant": {},
        "homeassistant.exceptions": {"ConfigEntryAuthFailed": AuthFailed},
        "homeassistant.helpers": {},
        "homeassistant.helpers.storage": {"Store": FakeStore},
        "homeassistant.helpers.update_coordinator": {
            "DataUpdateCoordinator": FakeCoordinator, "UpdateFailed": UpdateFailed,
        },
    }.items():
        modules[name] = types.ModuleType(name)
        modules[name].__dict__.update(attributes)
    spec = importlib.util.spec_from_file_location(
        "custom_components.eparkai.coordinator_test",
        Path(__file__).resolve().parents[1] / "custom_components/eparkai/coordinator.py",
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module.EParkaiCoordinator


Coordinator = load_coordinator()


class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        entry = types.SimpleNamespace(entry_id="entry", data={
            "username": "test", "password": "secret", "client_id": "123",
            "power_plant_id": "456", "object_address": "object", "interval_minutes": 60,
        })
        self.coordinator = Coordinator(FakeHass(), entry)
        self.day = datetime.now(TZ).date() - timedelta(days=1)
        self.intervals = parse_intervals(payload(day_samples(self.day)))

    async def asyncTearDown(self):
        self.coordinator.client.close()

    async def fetch(self, intervals=None):
        with patch.object(self.coordinator.client, "fetch", return_value=self.intervals if intervals is None else intervals):
            return await self.coordinator._async_update_data()

    async def test_empty_window_retains_both_readings(self):
        initial = await self.fetch()
        updated = await self.fetch([])
        self.assertEqual(initial["daily"], updated["daily"])
        self.assertEqual(initial["hourly"], updated["hourly"])
        self.assertFalse(updated["daily_in_response"])

    async def test_revisions_replace_and_older_windows_do_not_regress(self):
        await self.fetch()
        revised = parse_intervals(payload(day_samples(self.day, energy=2)))
        updated = await self.fetch(revised)
        self.assertEqual(updated["daily"]["energy"], 48)
        self.assertEqual(updated["hourly"]["energy"], 2)
        older = parse_intervals(payload(day_samples(self.day - timedelta(days=1))))
        updated = await self.fetch(older)
        self.assertEqual(updated["daily"]["energy"], 48)
        self.assertEqual(updated["daily"]["date"], self.day.isoformat())

    async def test_restart_loads_snapshot(self):
        initial = await self.fetch()
        self.coordinator.snapshot = {}
        await self.coordinator.async_load()
        self.assertEqual(self.coordinator.snapshot, initial)

    async def test_network_failure_preserves_cache_and_backs_off(self):
        initial = await self.fetch()
        for minutes in (5, 10, 20, 40, 60, 60):
            with patch.object(self.coordinator.client, "fetch", side_effect=requests.Timeout):
                with self.assertRaises(UpdateFailed):
                    await self.coordinator._async_update_data()
            self.assertEqual(self.coordinator.snapshot, initial)
            self.assertEqual(self.coordinator.update_interval, timedelta(minutes=minutes))
            # Home Assistant sets this after the coordinator raises UpdateFailed.
            self.coordinator.last_update_success = False
        await self.fetch()
        self.assertEqual(self.coordinator.update_interval, timedelta(hours=1))

    async def test_authentication_failure_requests_reauthentication(self):
        with patch.object(self.coordinator.client, "fetch", side_effect=AuthenticationError):
            with self.assertRaises(AuthFailed):
                await self.coordinator._async_update_data()


if __name__ == "__main__":
    unittest.main()
