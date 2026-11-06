# eParkai Insights for Home Assistant

**Since 0.3.0: historical hourly production graphs.** Overnight batches fill the original production hours instead of appearing at download time. [Set up the graph and Energy dashboard](HOURLY_GRAPHS.md#english).

[![Validate](https://github.com/Skirmantas-SK/eparkai-insights/actions/workflows/validate.yml/badge.svg)](https://github.com/Skirmantas-SK/eparkai-insights/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/Skirmantas-SK/eparkai-insights)](https://github.com/Skirmantas-SK/eparkai-insights/releases/latest)
![Home Assistant](https://img.shields.io/badge/Home_Assistant-2026.11.0%2B-blue)
[![MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

<img src="custom_components/eparkai_insights/brand/icon.png" alt="eParkai integration icon" width="128" height="128">

[Lietuviškas aprašas](README.md)

A custom integration with a historical hourly statistic and two summary kWh sensors per solar plant/object:

| Sensor | Reading |
| --- | --- |
| Latest day production | Total energy for the newest **complete day before today** in the provider's response |
| Latest hour production | Total energy for the newest **complete, elapsed hour**, independently of the daily selection |

For example, if November 5 has only three published hours but November 4 is
complete, the daily sensor shows November 4 and the hourly sensor shows the
latest complete hour from November 5. Zero production is valid data, including
nighttime hours. Missing or invalid intervals are never silently replaced by zero.

## Install

HA 2026.11 includes Marketplace. This repository is a custom repository, not yet
part of the default catalog. The integration is an independent community project,
not affiliated with eParkai or Ignitis.

[![Add repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Skirmantas-SK&repository=eparkai-insights&category=integration)
[![Set up integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=eparkai_insights)

With HACS, add `https://github.com/Skirmantas-SK/eparkai-insights` under **Custom
repositories**, select **Integration**, and download **eParkai**. Restart Home
Assistant and add **eParkai** under **Settings → Devices & services**.
Configuration uses a UI setup assistant; no `configuration.yaml` entry is needed.

Lithuanian setup, error messages, and sensor names are available when your Home
Assistant profile language is Lithuanian. English translations remain available.
The integration's listing name is **eParkai įžvalgos**.

For manual installation:

The bundled integration icon is available after installation in HA's Devices &
services screen. Light/dark and 256/512px
variants are included. This is original integration artwork, not the official
eParkai logo. Sensor entities use `mdi:solar-power`. The editable source is
`assets/eparkai.svg`; regenerate PNGs on Windows with `scripts/build-brand.ps1`.

1. Copy `custom_components/eparkai_insights` into your Home Assistant configuration's
   `custom_components` directory. The resulting path is
   `/config/custom_components/eparkai_insights/manifest.json` on a typical installation.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → eParkai Insights**.
4. Supply your login, client ID, plant ID, exact object address selector value,
   and sampling interval (60 minutes by default; 15 and 30 are supported).
5. Add another integration entry for each plant/object combination.

Requires Home Assistant 2026.11.0 or newer. Credentials are saved in Home Assistant's
config entry storage; keep that storage and backups private. Session cookies stay
in memory and are renewed after restart. No credentials belong in this repository.

Repository ZIP downloads contain the `custom_components/eparkai_insights` directory.
The GitHub repository can also be added to HACS as a custom integration repository.

### Migration and distinct identity

The new domain `eparkai_insights` is independent of `algirdasc/hass-eparkai`'s
`eparkai` domain. This integration provides period sensors and, since 0.3.0, its own hourly
external statistics. It does not overwrite the other component.
Both may coexist, but both will poll the portal.

If you installed **our 0.1.x versions**, back up HA, remove that config entry and
uninstall the old component through HACS, then install this repository and repeat
UI setup once. Config entries, entity IDs and cached readings are not migrated
across domains automatically. Update cards and automations. Existing history is
not rewritten. GitHub URL redirects do not migrate a Home Assistant domain.

### Why HACS may still show “icon not available”

Pre-install catalog icons and installed HA integration icons use different image
sources. Bundled `brand/` files work after installation. Before installation the
catalog needs to process the release's images; custom repositories outside the
catalog may have no icon. Older HACS frontends can also use the old brands CDN
after installation. Metadata, a README image, and a release alone cannot guarantee
that catalog thumbnail. Update HA/HACS, install, restart, then check **Devices &
services**. Report your HA/HACS versions if the icon is still absent there.
See [HA's branding documentation](https://contributors.home-assistant.io/marketplace/guides/integrations/#brand-images).

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

The two summary sensors are historical energy snapshots without a statistics state
class. Use the separate **Valandinė gamyba** external statistic for hourly graphs
and the Energy dashboard. See [the graph setup guide](HOURLY_GRAPHS.md#english).

The portal is not a documented public API. Labels are assumed to denote interval
starts, as in the supplied protocol guide; this convention and units need live
account verification. Only the returned week window is searched; there is no
older-history pagination. No live account credentials were supplied during development.

## Development

Run `python -m unittest discover -s tests -v` with Python 3.13 and `requests` installed.
Windows also needs `tzdata`. Run `python -m compileall -q custom_components tests`
for a syntax check. Tests use synthetic responses and do not contact the portal.
Offline coordinator tests use HA boundary doubles. A separate CI suite uses the
actual Home Assistant library (2026.11.0 and latest stable), exercising config
flow, coordinator, storage, lifecycle APIs and sensor metadata with mocked portal
I/O and platform forwarding. A live account and full HA UI scenario remain
unverified. See [Actions](https://github.com/Skirmantas-SK/eparkai-insights/actions)
for current check results, including imports into a real HA SQLite recorder, and [CONTRIBUTING.md](CONTRIBUTING.md) for commands.

[Changelog](CHANGELOG.md) · [Security](SECURITY.md) · [MIT license](LICENSE)

The implementation follows the website protocol from
[algirdasc/hass-eparkai](https://github.com/algirdasc/hass-eparkai)
(reviewed at commit `cc05ea2af1f2ffd54f6f9c6ca4a502a3bf2175d5`) and the supplied
[EPARKAI_INTEGRATION.md](EPARKAI_INTEGRATION.md). The provider and aggregation code
is newly implemented here, with stricter validation and independently selected
daily/hourly readings. Home Assistant's
[coordinator](https://developers.home-assistant.io/docs/integration_fetching_data/)
and [config flow](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
patterns provide polling and UI setup.
