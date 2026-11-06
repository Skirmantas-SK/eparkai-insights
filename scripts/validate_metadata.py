"""Validate repository identity, translations, version, and PNG packaging offline."""

import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "eparkai_insights"
COMPONENT = ROOT / "custom_components" / DOMAIN


def leaf_keys(value, prefix=""):
    result = set()
    for key, item in value.items():
        path = f"{prefix}{key}"
        if isinstance(item, dict):
            result.update(leaf_keys(item, path + "."))
        else:
            assert isinstance(item, str) and item.strip(), path
            result.add(path)
    return result


manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
assert manifest["domain"] == DOMAIN
assert manifest["name"] == hacs["name"] == "eParkai įžvalgos"
assert manifest["documentation"] == "https://github.com/Skirmantas-SK/eparkai-insights"
assert manifest["issue_tracker"] == manifest["documentation"] + "/issues"
assert hacs["country"] == "LT"
assert hacs["homeassistant"] == "2026.11.0"
assert manifest["requirements"] == [], "Use HA's requests dependency"
assert f'## {manifest["version"]}' in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
source = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
for language in ("en", "lt"):
    translation = json.loads((COMPONENT / "translations" / f"{language}.json").read_text(encoding="utf-8"))
    assert leaf_keys(source) == leaf_keys(translation), language
for filename, size in (("icon.png", 256), ("icon@2x.png", 512), ("dark_icon.png", 256), ("dark_icon@2x.png", 512)):
    data = (COMPONENT / "brand" / filename).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", filename
    assert struct.unpack(">II", data[16:24]) == (size, size), filename
    assert data[25] == 6, f"{filename}: expected RGBA transparency"
print(f"Metadata, translations and brand assets valid for {DOMAIN} {manifest['version']}")
