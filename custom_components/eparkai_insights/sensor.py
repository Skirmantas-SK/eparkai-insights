"""Latest complete day and latest complete hour of production, in kWh."""

from datetime import date, datetime, timedelta, timezone

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .production import TZ
from .statistics_import import statistic_id

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([EParkaiSensor(entry.runtime_data, key) for key in ("daily", "hourly")])
    async_add_entities([EParkaiDataDate(entry.runtime_data), EParkaiImportStatus(entry.runtime_data)])


class EParkaiSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:solar-power"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 3
    # These are historical period snapshots, not cumulative meters. A total or
    # total_increasing state class would miscount revisions and repeated polls.
    _attr_state_class = None

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.entry.unique_id}_{key}"
        self._attr_entity_registry_enabled_default = key != "hourly"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.unique_id)},
            name=coordinator.entry.title, manufacturer="eParkai",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def reading(self):
        return self.coordinator.snapshot.get(self.key)

    @property
    def available(self):
        # Retain cached readings through transient failures; expose freshness below.
        return self.reading is not None

    @property
    def native_value(self):
        return self.reading["energy"] if self.reading else None

    @property
    def extra_state_attributes(self):
        now = datetime.now(timezone.utc)
        reading = self.reading
        last_fetch = self.coordinator.snapshot.get("last_successful_fetch")
        stale = True
        if reading:
            validated = datetime.fromisoformat(reading["validated_at"])
            if self.key == "daily":
                old_measurement = datetime.fromisoformat(reading["date"]).date() < now.astimezone(TZ).date() - timedelta(days=1)
            else:
                old_measurement = now - datetime.fromisoformat(reading["end"]) > timedelta(hours=3)
            stale = old_measurement or now - validated > timedelta(hours=3)
        attributes = {
            "last_successful_fetch": last_fetch,
            "last_update_success": self.coordinator.last_update_success,
            "is_stale": stale or not self.coordinator.last_update_success,
            "period_available_in_response": self.coordinator.snapshot.get(f"{self.key}_in_response", False),
            "timezone": "Europe/Vilnius",
            "statistic_id": statistic_id(self.coordinator.entry),
            "statistics_import_status": self.coordinator.snapshot.get("statistics_import_status", "pending"),
            "last_statistics_import": self.coordinator.snapshot.get("last_statistics_import"),
        }
        if reading:
            attributes.update({key: value for key, value in reading.items() if key != "energy"})
        return attributes


class EParkaiDataDate(EParkaiSensor):
    """The Lithuanian calendar date belonging to the displayed daily total."""

    _attr_device_class = SensorDeviceClass.DATE
    _attr_native_unit_of_measurement = None
    _attr_suggested_display_precision = None
    _attr_icon = "mdi:calendar"

    def __init__(self, coordinator):
        super().__init__(coordinator, "daily")
        self._attr_translation_key = "data_date"
        self._attr_unique_id = f"{coordinator.entry.unique_id}_data_date"

    @property
    def native_value(self):
        return date.fromisoformat(self.reading["date"]) if self.reading else None

    @property
    def extra_state_attributes(self):
        return {"timezone": "Europe/Vilnius"}


class EParkaiImportStatus(CoordinatorEntity, SensorEntity):
    """Show history readiness in the device page without digging into attributes."""

    _attr_has_entity_name = True
    _attr_translation_key = "import_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = ["pending", "imported", "failed", "no_data"]

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.unique_id}_import_status"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.entry.unique_id)})

    @property
    def available(self):
        return True

    @property
    def native_value(self):
        return self.coordinator.snapshot.get("statistics_import_status", "pending")

    @property
    def extra_state_attributes(self):
        return {"statistic_id": statistic_id(self.coordinator.entry),
                "last_statistics_import": self.coordinator.snapshot.get("last_statistics_import"),
                "imported_hours": self.coordinator.snapshot.get("imported_hours", 0)}
