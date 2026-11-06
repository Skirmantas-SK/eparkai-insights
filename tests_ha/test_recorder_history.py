"""Import and read actual historical statistics using HA's SQLite recorder."""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.config_entries import ConfigEntries
from homeassistant import loader
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.helpers.recorder import async_initialize_recorder
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period

from custom_components.eparkai_insights.statistics_import import StatisticsImporter


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
