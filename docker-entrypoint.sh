#!/bin/sh
set -eu

PLUGIN_DIR="$HERMES_HOME/plugins/bale"
mkdir -p "$PLUGIN_DIR"
cp /opt/hermes/bale-plugin/adapter.py "$PLUGIN_DIR/adapter.py"
cp /opt/hermes/bale-plugin/__init__.py "$PLUGIN_DIR/__init__.py"
cp /opt/hermes/bale-plugin/plugin.yaml "$PLUGIN_DIR/plugin.yaml"

python - <<'PY'
import os
from pathlib import Path
import yaml

home = Path(os.environ["HERMES_HOME"])
config_path = home / "config.yaml"
if config_path.exists():
    config = yaml.safe_load(config_path.read_text()) or {}
else:
    config = {}

plugins = config.setdefault("plugins", {})
enabled = plugins.setdefault("enabled", [])
if not isinstance(enabled, list):
    enabled = []
for name in ("bale", "bale-platform"):
    if name not in enabled:
        enabled.append(name)
plugins["enabled"] = enabled

disabled = plugins.get("disabled")
if isinstance(disabled, list):
    plugins["disabled"] = [
        name for name in disabled if name not in {"bale", "bale-platform"}
    ]

platforms = config.setdefault("platforms", {})
bale = platforms.setdefault("bale", {})
bale["enabled"] = True
platforms["bale"] = bale

config_path.write_text(
    yaml.safe_dump(config, sort_keys=False, allow_unicode=True)
)
PY

exec hermes gateway run
