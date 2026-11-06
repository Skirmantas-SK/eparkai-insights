"""Import and read actual historical statistics using HA's SQLite recorder."""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.config_entries import ConfigEntries
from homeassistant import loader
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.helpers.recorder import async_initialize_recorder
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.components.recorder.statistics import list_statistic_ids
from homeassistant.components.energy.data import async_get_manager
from homeassistant.components.energy.validate import async_validate
from homeassistant.helpers import device_registry, entity_registry

from custom_components.eparkai_insights.statistics_import import StatisticsImporter
from custom_components.eparkai_insights.energy import async_connect_energy


class RecorderHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.hass = HomeAssistant(self.directory.name)
        self.addAsyncCleanup(self.hass.async_stop, force=True)
        loader.async_setup(self.hass)
        async_initialize_recorder(self.hass)
        self.hass.config_entries = ConfigEntries(self.hass, {})
        await self.hass.config_entries.async_initialize()
        device_registry.async_setup(self.hass)
        await device_registry.async_load(self.hass)
        await entity_registry.async_load(self.hass)
        self.assertTrue(await async_setup_component(self.hass, "recorder", {
            "recorder": {"db_url": f"sqlite:///{self.directory.name}/history.db", "commit_interval": 0}
        }))
        await self.hass.async_start()
        self.recorder = get_instance(self.hass)
        async with asyncio.timeout(30):
            await self.recorder.async_block_till_done()
        self.entry = SimpleNamespace(unique_id="synthetic_plant", title="Synthetic plant")
        self.importer = StatisticsImporter(self.hass, self.entry)
        self.start = datetime(2026, 10, 25, 0, tzinfo=timezone.utc)

    def hours(self, values):
        return [{"start": (self.start + timedelta(hours=index)).isoformat(), "energy": energy}
                for index, energy in enumerate(values)]

    async def read(self):
        result = await self.recorder.async_add_executor_job(
            statistics_during_period, self.hass, self.start, None,
            {self.importer.statistic_id}, "hour", None, {"state", "sum", "change"},
        )
        return result[self.importer.statistic_id]

    async def test_graph_has_hourly_curve_at_source_times_not_fetch_time(self):
        values = [0, 0.2, 1.5, 0.6, 0]
        await self.importer.async_import(self.hours(values))
        rows = await self.read()
        self.assertEqual(len(rows), 5)
        self.assertEqual([round(row["change"], 6) for row in rows], values)
        self.assertEqual([row["state"] for row in rows], values)
        self.assertEqual([row["start"] for row in rows],
                         [(self.start + timedelta(hours=i)).timestamp() for i in range(5)])
        # A new importer instance simulates restart; replaying the batch is safe.
        self.importer = StatisticsImporter(self.hass, self.entry)
        await self.importer.async_import(self.hours(values))
        self.assertEqual(await self.read(), rows)

    async def test_correction_rewrites_existing_tail_and_gap_fill(self):
        hours = self.hours([0.1, 0.2, 0.3, 0.4])
        await self.importer.async_import([hours[0], hours[2], hours[3]])
        await self.importer.async_import([hours[1]])
        rows = await self.read()
        self.assertEqual([round(row["change"], 6) for row in rows], [0.1, 0.2, 0.3, 0.4])
        await self.importer.async_import([{**hours[1], "energy": 0.8}])
        rows = await self.read()
        self.assertEqual([round(row["change"], 6) for row in rows], [0.1, 0.8, 0.3, 0.4])
        self.assertAlmostEqual(rows[-1]["sum"], 1.6)

    async def test_new_window_keeps_earlier_total_and_objects_are_isolated(self):
        await self.importer.async_import(self.hours([1, 2]))
        late = {"start": (self.start + timedelta(days=2)).isoformat(), "energy": 4}
        await self.importer.async_import([late])
        self.assertEqual((await self.read())[-1]["sum"], 7)
        other = StatisticsImporter(self.hass, SimpleNamespace(unique_id="other_object", title="Other object"))
        await other.async_import(self.hours([9]))
        self.assertEqual((await self.read())[-1]["sum"], 7)

    async def test_series_is_discoverable_by_graph_and_energy_pickers(self):
        await self.importer.async_import(self.hours([0, 0.5, 2, 0]))
        # This is the same metadata API used by recorder/list_statistic_ids and
        # the Statistics graph / Energy pickers, not merely a direct SQL query.
        metadata = await self.recorder.async_add_executor_job(
            list_statistic_ids, self.hass, {self.importer.statistic_id},
        )
        self.assertEqual(len(metadata), 1)
        self.assertEqual(metadata[0]["unit_class"], "energy")
        self.assertTrue(metadata[0]["has_sum"])
        self.assertIn("Valandinė gamyba", metadata[0]["name"])

    async def test_energy_remote_setup_is_valid_idempotent_and_keeps_preferences(self):
        await self.importer.async_import(self.hours([0, 0.5, 2, 0]))
        manager = await async_get_manager(self.hass)
        # Preserve unrelated preferences exactly, including a user-added source.
        existing = {"type": "solar", "stat_energy_from": "other:solar", "name": "Existing"}
        await manager.async_update({"energy_sources": [existing], "device_consumption": []})
        await async_connect_energy(self.hass, self.entry, "remote")
        await async_connect_energy(self.hass, self.entry, "remote")
        sources = manager.data["energy_sources"]
        self.assertEqual(len(sources), 3)
        self.assertEqual(sources[0], existing)
        self.assertEqual(sources[1]["stat_energy_from"], self.importer.statistic_id)
        self.assertEqual(sources[2]["stat_energy_to"], self.importer.statistic_id)
        self.assertIsNone(sources[2]["stat_energy_from"])
        # HA's actual Energy validator must accept our solar AND export source.
        validation = (await async_validate(self.hass)).as_dict()
        self.assertEqual(validation["energy_sources"][1:], [[], []])

    async def test_energy_setup_refuses_missing_history(self):
        with self.assertRaises(ValueError):
            await async_connect_energy(self.hass, self.entry, "remote")
        manager = await async_get_manager(self.hass)
        self.assertIsNone(manager.data)

    async def test_import_does_not_report_success_when_recorder_drops_batch(self):
        with patch("custom_components.eparkai_insights.statistics_import.async_add_external_statistics"):
            with self.assertRaisesRegex(RuntimeError, "did not persist"):
                await self.importer.async_import(self.hours([1, 2]))

    async def test_energy_solar_and_export_can_be_added_individually(self):
        await self.importer.async_import(self.hours([1, 2]))
        await async_connect_energy(self.hass, self.entry, "solar")
        manager = await async_get_manager(self.hass)
        self.assertEqual([s["type"] for s in manager.data["energy_sources"]], ["solar"])
        await async_connect_energy(self.hass, self.entry, "export")
        self.assertEqual([s["type"] for s in manager.data["energy_sources"]], ["solar", "grid"])
