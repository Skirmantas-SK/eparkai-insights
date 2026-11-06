# eParkai Solar Production for Home Assistant

A custom integration with two kWh sensors per solar plant/object:

| Sensor | Reading |
| --- | --- |
| Latest day production | Total energy for the newest **complete day before today** in the provider's response |
| Latest hour production | Total energy for the newest **complete, elapsed hour**, independently of the daily selection |

For example, if November 5 has only three published hours but November 4 is
complete, the daily sensor shows November 4 and the hourly sensor shows the
latest complete hour from November 5. Zero production is valid data, including
nighttime hours. Missing or invalid intervals are never silently replaced by zero.

## Install

1. Copy `custom_components/eparkai` into your Home Assistant configuration's
   `custom_components` directory. The resulting path is
   `/config/custom_components/eparkai/manifest.json` on a typical installation.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → eParkai Solar Production**.
4. Supply your login, client ID, plant ID, exact object address selector value,
   and sampling interval (60 minutes by default; 15 and 30 are supported).
5. Add another integration entry for each plant/object combination.

Requires Home Assistant 2025.1 or newer. Credentials are saved in Home Assistant's
config entry storage; keep that storage and backups private. Session cookies stay
in memory and are renewed after restart. No credentials belong in this repository.

Repository ZIP downloads contain the `custom_components/eparkai` directory.
This repository is hosted on a private Git service; manual installation is the
supported route. The included HACS metadata also permits a future GitHub mirror.

If replacing `algirdasc/hass-eparkai`, back up the old component, replace its
`custom_components/eparkai` directory, and remove its `eparkai:` YAML block before
restarting. This integration uses the same domain and cannot run alongside it.
It creates sensors and does not continue the old external-statistics importer.
Existing recorded statistics are not deleted.

## Find the IDs

Sign in at [eParkai](https://www.eparkai.lt), then visit the generation page.
The number in `/user/12345/generation` is the client ID. In the page source, find
the `generation_electricity` selector and use the plant's option value. Use the
exact option value from the `address` / `edit-address` selector for the object
address, including punctuation and spacing. Leave it blank only when no object
selection is needed. IDs are strings, so leading zeros are retained.

## Data and freshness

The integration fetches the provider's week view at startup and every hour.
Transient failures retry after 5 minutes, doubling to a maximum of 60 minutes.
Authentication failures trigger Home Assistant's reauthentication flow and stop
automatic password attempts until reauthentication or reload. If prompted, log
into the portal in a browser and confirm contact information first.

Daily attributes include `date`, `last_interval`, and `interval_count`. Hourly
attributes include `start`, `end`, `source_labels`, and `interval_count`.
Both sensors expose `validated_at`, `last_successful_fetch`, `last_update_success`,
`period_available_in_response`, and `is_stale`.

The latest validated reading is persisted through restarts and retained when a
response has no complete period or a subsequent request fails. Without a stored
reading the corresponding sensor is unavailable. Initial network/authentication
failures defer setup until connectivity/login is restored; cached readings are
loaded when setup succeeds. A valid hourly reading can exist without a daily one.
Corrected values replace a period's previous reading; they are never added twice.

Daily data is stale when older than yesterday in Lithuania; hourly data is stale
when its end is more than three hours ago. Either is also stale after three hours
without validation of that reading, or after a failed update. Freshness is
evaluated on coordinator updates. Delayed but valid provider readings can be stale.

All calendar calculations use `Europe/Vilnius`, regardless of the HA timezone.
Complete days require all expected valid samples, including 23/25-hour daylight
saving days. Autumn's repeated hour remains two distinct hours with different
UTC offsets. Without both repeated labels, an ambiguous hour is not published.
For 15/30-minute data, the hourly sensor sums all samples in the hour.

These are **historical energy snapshots**, not instantaneous power or cumulative
meters. They intentionally have no statistics state class and should not be used
as `total_increasing` Energy Dashboard sources. They work in entity cards,
history views, and automations. Historical Energy Dashboard import is outside
this integration's scope.

The portal is not a documented public API. Labels are assumed to denote interval
starts, as in the supplied protocol guide; this convention and units need live
account verification. Only the returned week window is searched; there is no
older-history pagination. No live account credentials were supplied during development.

## Development

Run `python -m unittest discover -s tests -v` with Python 3.13 and `requests` installed.
Windows also needs `tzdata`. Run `python -m compileall -q custom_components tests`
for a syntax check. Tests use synthetic responses and do not contact the portal.
Coordinator tests use lightweight Home Assistant boundary doubles; a full Home
Assistant runtime/config-flow test and live account test have not been run.

The implementation follows the website protocol from
[algirdasc/hass-eparkai](https://github.com/algirdasc/hass-eparkai)
(reviewed at commit `cc05ea2af1f2ffd54f6f9c6ca4a502a3bf2175d5`) and the supplied
[EPARKAI_INTEGRATION.md](EPARKAI_INTEGRATION.md). The provider and aggregation code
is newly implemented here, with stricter validation and independently selected
daily/hourly readings. Home Assistant's
[coordinator](https://developers.home-assistant.io/docs/integration_fetching_data/)
and [config flow](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
patterns provide polling and UI setup.
