# Historical energy: implementation findings

Checked against Home Assistant Core 2026.11.0 and its current frontend, November 2026.

## Backdated data is supported

HA's `async_add_external_statistics` accepts timezone-aware, top-of-hour timestamps.
Each source hour is inserted at that timestamp, independently of when the provider
publishes it. This is the correct path for delayed energy batches. A normal entity
state update records its arrival time; changing a snapshot sensor to
`total_increasing` would count nightly changes at the wrong time and mishandle
revisions. We intentionally keep the two snapshot sensors out of automatic energy
statistics and publish a separate, stable external statistic.

Sources:
- [Core recorder import implementation](https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/components/recorder/statistics.py)
- [HA Opower integration: delayed utility data](https://www.home-assistant.io/integrations/opower/)
- [Statistics storage](https://contributors.home-assistant.io/data/reference/statistics/)

## Why the summary sensor cannot be selected

The Statistics graph and Energy use statistic metadata, not just the sensor list.
External IDs use `eparkai_insights:...` rather than `sensor....`. The frontend's
statistic picker explicitly supports these IDs. Energy's solar and grid settings
use that same picker with an energy unit-class filter. Our series has
`unit_class: energy`, `unit_of_measurement: kWh`, `has_sum: true`, and no mean.

Sources:
- [Statistic picker](https://github.com/home-assistant/frontend/blob/dev/src/components/entity/ha-statistic-picker.ts)
- [Solar source picker](https://github.com/home-assistant/frontend/blob/dev/src/panels/config/energy/dialogs/dialog-energy-solar-settings.ts)
- [Grid source picker](https://github.com/home-assistant/frontend/blob/dev/src/panels/config/energy/dialogs/dialog-energy-grid-settings.ts)
- [HA Energy validation](https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/components/energy/validate.py)

Version 0.4.0 removes manual selection from the required setup path: Configure
imports data, verifies metadata discovery, validates the Energy source schema,
and appends the selected roles through HA's Energy manager. No internal storage
files or SQL tables are edited. Existing meters, names and price settings remain.
The same source is not added twice. Sources are added only when the user submits
the options flow, so removing one later in Energy settings is respected.

## Remote generation and export

Reporting delay does not define the direction of energy flow. Solar production is
generation; grid export is energy delivered to the grid. For a remote plant whose
entire output is exported, the same measured quantity can feed a solar source and
a separate export-only connection. Together these represent generation sent to
the grid without falsely assigning it to household self-consumption. Do not add
remote export to the household grid meter. Select solar-only if export is unknown.

This follows [HA's dedicated solar export guidance](https://www.home-assistant.io/docs/energy/faq/#setting-up-a-dedicated-solar-export-connection-in-the-energy-dashboard).
We do not fabricate instantaneous power or tariff compensation from delayed kWh.

## Verification

Real-HA SQLite tests cover source timestamps, hourly changes, repeated imports,
restart replay, missing-hour insertion, corrected historical totals, statistic
picker metadata, solar/export validation, and preserving existing Energy sources.
The importer reads its rows back before reporting success. The options form
refuses to connect a missing or failed import. Offline tests additionally cover
Lithuanian time-zone transitions and 15/30/60-minute source intervals.

The Energy dashboard's date selector must point to a published day. Its default
today view can legitimately be empty for an overnight or delayed provider. HA's
display time zone controls chart labels; source times are stored as UTC, derived
from Europe/Vilnius. Long-term statistics survive the provider's rolling window;
we cannot recover older periods that the portal no longer returns.
