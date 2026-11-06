"""Poll once for both sensors and persist the last validated readings."""

from datetime import datetime, timedelta, timezone
import logging

import requests
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AuthenticationError, EParkaiClient
from .const import CONF_ADDRESS, CONF_INTERVAL, CONF_PLANT_ID, DOMAIN
from .production import ParseError, TZ, select_production

_LOGGER = logging.getLogger(__name__)


class EParkaiCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(hours=1))
        self.entry = entry
        self.client = EParkaiClient(entry.data["username"], entry.data["password"], entry.data["client_id"])
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.snapshot = {"daily": None, "hourly": None, "last_successful_fetch": None}
        self.statistics_importer = None
        self.pending_hours = []

    async def async_load(self):
        cached = await self.store.async_load()
        if isinstance(cached, dict):
            self.snapshot.update(cached)

    async def _async_update_data(self):
        now = datetime.now(timezone.utc)
        try:
            intervals = await self.hass.async_add_executor_job(
                self.client.fetch, self.entry.data[CONF_PLANT_ID],
                self.entry.data.get(CONF_ADDRESS, ""), now.astimezone(TZ),
            )
            selected = select_production(intervals, self.entry.data[CONF_INTERVAL], now)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("Check eParkai credentials or confirm contact details in the portal") from err
        except (requests.RequestException, ParseError) as err:
            # Do not include request bodies, tokens or account HTML in logs.
            retry_minutes = 5
            if not self.last_update_success:
                retry_minutes = min(self.update_interval.total_seconds() / 60 * 2, 60)
            self.update_interval = timedelta(minutes=retry_minutes)
            raise UpdateFailed("Unable to retrieve valid eParkai generation data") from err
        self.update_interval = timedelta(hours=1)
        snapshot = dict(self.snapshot)
        for key, time_key in (("daily", "date"), ("hourly", "start")):
            value = selected[key]
            old = snapshot[key]
            if value is not None:
                # Revisions replace the same period; older windows never regress sensors.
                new_time = datetime.fromisoformat(value[time_key])
                old_time = datetime.fromisoformat(old[time_key]) if old else None
                if old_time is None or new_time >= old_time:
                    snapshot[key] = {**value, "validated_at": now.isoformat()}
            snapshot[f"{key}_in_response"] = value is not None
        snapshot["last_successful_fetch"] = now.isoformat()
        self.pending_hours = selected["hours"]
        await self.store.async_save(snapshot)
        self.snapshot = snapshot
        if self.statistics_importer is not None and self.hass.is_running:
            await self.async_import_history()
        return snapshot

    async def async_import_history(self):
        """Import source-time history without treating it as live sensor updates."""
        if self.statistics_importer is None or not self.pending_hours:
            return
        try:
            await self.statistics_importer.async_import(self.pending_hours)
        except Exception:
            # Recorder failure must not discard a valid portal snapshot. Retry
            # on the next poll; database exceptions contain no portal credentials.
            _LOGGER.exception("Unable to import eParkai hourly statistics")
            self.snapshot["statistics_import_status"] = "failed"
            self.update_interval = timedelta(minutes=5)
        else:
            self.snapshot["statistics_import_status"] = "imported"
            self.snapshot["last_statistics_import"] = datetime.now(timezone.utc).isoformat()
        self.async_update_listeners()
