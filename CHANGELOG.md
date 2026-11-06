# Pakeitimai / Changelog

## 0.4.1

- Keep the latest complete day's production and add a visible Data date sensor
  showing that same day's Lithuanian calendar date, including cached readings.
- Disable the latest-hour summary sensor by default for new entities. Existing
  entity preferences are preserved; it can still be enabled in entity settings.
- Keep the import-status sensor and historical hourly Energy series unchanged.

## 0.4.0

- Add an integration Configure flow that imports history, verifies statistic
  discovery, and connects it directly to Energy without YAML or copying IDs.
- Support solar, export-only, and remote production + separate full export.
  Existing household sources and costs are preserved; repeat setup is idempotent.
- Add a translated History import diagnostic sensor and persist import status.
- Read hourly rows back from recorder before reporting a successful import.
- Test HA's actual statistic-picker metadata and Energy validation APIs, including
  both solar and grid-export sources and preservation of existing preferences.
- Clarify that delayed production is historical energy, not live power, and that
  export must reflect the actual connection rather than the reporting delay.

## 0.3.0

- Import every complete hour from the portal's returned window into HA long-term
  statistics at the original measurement time, even when published overnight.
- Add a named `Valandinė gamyba` series for hourly Statistics Graph and Energy
  Dashboard use; summary sensors expose its `statistic_id` and import status.
- Replay batches safely after restart; revisions replace hours and recompute the
  later cumulative totals. Missing new samples preserve previously valid history.
- Preserve Lithuanian timezone and both autumn hours; aggregate 15/30-minute input.
- Expose the latest complete day's timestamped `hours` attribute for custom charts.
- Recorder is now a required HA dependency. Existing configuration remains valid.

## 0.2.1

- Clarify that object address is optional and expects the portal option value,
  not a manually typed street address.
- Include the specific safe parser failure reason in setup/reauth errors instead
  of implying all unsupported responses are caused by incorrect plant/object IDs.
- Match the reference parser by ignoring non-chart Drupal settings when selecting
  the generation series; still reject multiple actual chart series.
- Live portal verification remains pending; the reported account-specific failure
  is not confirmed resolved.

## 0.2.0

- Naujas pavadinimas **eParkai įžvalgos** ir atskiras domenas `eparkai_insights`.
- New repository identity, independent of `algirdasc/hass-eparkai`.
- Target Home Assistant 2026.11.0 and newer; use HA's own requests dependency.
- Use the current probatio setup-form schema API and current GitHub Actions.
- Add solar category, Lithuanian country metadata, GitHub description/topics,
  issue templates, contribution/security guidance, and MIT license.
- Add hassfest, HACS, offline regression, and real HA runtime CI checks.
- Keep bundled light/dark icons; explain pre-install catalog icon limitations.
- Breaking change: users of versions 0.1.x must remove the old integration and
  configure the new domain once. Existing history is not migrated automatically.

## 0.1.2

- Bundled integration icons and solar sensor icon.

## 0.1.1

- Lithuanian translations and GitHub/HACS installation documentation.

## 0.1.0

- Initial latest complete day and hour sensors, UI setup, caching and reauthentication.
