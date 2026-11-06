"""Connect verified historical statistics to HA Energy without manual IDs."""

from homeassistant.components.energy.data import ENERGY_SOURCE_SCHEMA, async_get_manager
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import list_statistic_ids

from .statistics_import import statistic_id


async def async_connect_energy(hass, entry, mode):
    """Add requested roles, preserving all existing meters and preferences."""
    if mode == "manual":
        return
    if mode not in ("solar", "export", "remote"):
        raise ValueError("Unknown energy connection mode")
    series = statistic_id(entry)
    metadata = await get_instance(hass).async_add_executor_job(
        list_statistic_ids, hass, {series}, "sum",
    )
    if not any(row["statistic_id"] == series and row["unit_class"] == "energy"
               and row["has_sum"] for row in metadata):
        raise ValueError("Hourly statistics are not available yet")
    manager = await async_get_manager(hass)
    sources = list((manager.data or manager.default_preferences())["energy_sources"])
    if mode in ("solar", "remote") and not any(
        item["type"] == "solar" and item.get("stat_energy_from") == series for item in sources
    ):
        sources.append({"type": "solar", "stat_energy_from": series, "name": entry.title})
    if mode in ("export", "remote") and not any(
        item["type"] == "grid" and item.get("stat_energy_to") == series for item in sources
    ):
        sources.append({"type": "grid", "stat_energy_from": None, "stat_energy_to": series,
                        "cost_adjustment_day": 0.0, "name": entry.title})
    sources = ENERGY_SOURCE_SCHEMA(sources)
    await manager.async_update({"energy_sources": sources})
