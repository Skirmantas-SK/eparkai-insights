"""Home Assistant integration for the latest eParkai production readings."""

from homeassistant.const import Platform
from homeassistant.helpers.start import async_at_started

from .coordinator import EParkaiCoordinator
from .statistics_import import StatisticsImporter

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass, entry):
    coordinator = EParkaiCoordinator(hass, entry)
    try:
        await coordinator.async_load()
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await hass.async_add_executor_job(coordinator.client.close)
        raise
    entry.runtime_data = coordinator
    coordinator.statistics_importer = StatisticsImporter(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def import_after_start(_hass):
        await coordinator.async_import_history()

    # Avoid blocking startup on recorder's queue, which starts processing only
    # after Home Assistant has finished starting.
    entry.async_on_unload(async_at_started(hass, import_after_start))
    return True


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.async_add_executor_job(entry.runtime_data.client.close)
        return True
    return False


async def async_remove_entry(hass, entry):
    from homeassistant.helpers.storage import Store
    from .const import DOMAIN

    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()
