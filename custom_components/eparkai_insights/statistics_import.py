"""Import delayed provider batches into Home Assistant's hourly recorder."""

import asyncio
from datetime import datetime, timezone

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.tasks import SynchronizeTask
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics, get_last_statistics, statistics_during_period,
)
from homeassistant.const import UnitOfEnergy

from .const import DOMAIN
from .history import build_statistics


def statistic_id(entry):
    """Keep the series stable across restarts, renames and reauthentication."""
    return f"{DOMAIN}:generation_{entry.unique_id}"


class StatisticsImporter:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.statistic_id = statistic_id(entry)
        self._lock = asyncio.Lock()

    async def _async_wait_for_recorder(self, recorder):
        """Always enqueue a barrier, including when a task is already executing."""
        # async_block_till_done can return early when the queue is empty while
        # an external-statistics task is still committing its own DB session.
        future = self.hass.loop.create_future()
        recorder.queue_task(SynchronizeTask(future))
        await future

    async def async_import(self, hours):
        if not hours:
            return
        async with self._lock:
            recorder = get_instance(self.hass)
            # Called only after HA starts: recorder waits for startup before
            # processing its queue. Drain prior imports before reading the anchor.
            async with asyncio.timeout(30):
                await self._async_wait_for_recorder(recorder)
                start = min(datetime.fromisoformat(row["start"]).astimezone(timezone.utc) for row in hours)
                recorded = await recorder.async_add_executor_job(
                    statistics_during_period, self.hass, start, None,
                    {self.statistic_id}, "hour", None, {"state", "sum"},
                )
                existing = recorded.get(self.statistic_id, [])
                previous_sum = 0.0
                if not existing:
                    previous = await recorder.async_add_executor_job(
                        get_last_statistics, self.hass, 1, self.statistic_id, True, {"sum"},
                    )
                    if rows := previous.get(self.statistic_id):
                        previous_sum = rows[-1]["sum"] or 0.0
                statistics = build_statistics(hours, existing, previous_sum)
                metadata = {
                    "statistic_id": self.statistic_id,
                    "source": DOMAIN,
                    "name": f"{self.entry.title} – Valandinė gamyba",
                    "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                    "unit_class": "energy",
                    "has_sum": True,
                    "mean_type": StatisticMeanType.NONE,
                }
                async_add_external_statistics(self.hass, metadata, statistics)
                await self._async_wait_for_recorder(recorder)
