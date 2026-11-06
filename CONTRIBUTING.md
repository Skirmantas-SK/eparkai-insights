# Prisidėjimas / Contributing

Issues and pull requests are welcome in Lithuanian or English. Start with a small,
reproducible example and never include real account pages or credentials.

Use Python 3.14.2 or newer for Home Assistant 2026.11. The offline data tests also
run on Python 3.13:

```sh
python -m pip install requests tzdata
python -m unittest discover -s tests -v
python scripts/validate_metadata.py
```

On Linux, install the supported Home Assistant release and run the separate
runtime suite in a fresh process (the offline suite uses HA boundary doubles):

```sh
python -m pip install homeassistant==2026.11.0
python -m unittest discover -s tests_ha -v
```

GitHub Actions also run hassfest, HACS validation, and runtime checks against the
latest stable HA package. Keep translations in `translations/en.json` and
`translations/lt.json` aligned. `strings.json` is the development source only.
Do not translate entity unique IDs, attribute keys, or stored config keys.

Before releasing: update the manifest version and CHANGELOG, wait for every
validation job to pass, create a matching semantic version tag, and publish a
GitHub Release. HACS uses releases for named versions instead of commit hashes.
Do not claim live portal verification unless an actual authenticated test ran.

The integration's provider implementation is original code informed by
algirdasc/hass-eparkai and the supplied protocol guide; preserve that attribution.
The artwork in `assets/eparkai.svg` is an original integration icon, not an
official eParkai company logo. Rebuild the PNGs with `scripts/build-brand.ps1`.
