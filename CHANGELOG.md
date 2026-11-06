# Pakeitimai / Changelog

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
