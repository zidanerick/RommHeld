from __future__ import annotations

import json
from pathlib import Path

from .platform_services import APP_NAME, cache_dir, config_path

# Preserve the current Linux config location for migration only.
LEGACY_APP_DIR = Path.home() / ".config" / "romm-vita-manager"
LEGACY_CONFIG_PATH = LEGACY_APP_DIR / "config.json"

CONFIG_PATH = config_path()
APP_DIR = CONFIG_PATH.parent
DEFAULT_ROMM_ROOT = Path.home() / "RomM" / "roms" / "roms"


def _load_path(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_config() -> dict:
    value = _load_path(CONFIG_PATH)
    if value:
        return value

    # One-time migration from the old Linux-only location.
    if LEGACY_CONFIG_PATH != CONFIG_PATH:
        legacy = _load_path(LEGACY_CONFIG_PATH)
        if legacy:
            save_config(legacy)
            return legacy
    return {}


def save_config(config: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, indent=2), encoding="utf-8")
    temporary.replace(CONFIG_PATH)


def package_cache_dir() -> Path:
    path = cache_dir() / "packages"
    path.mkdir(parents=True, exist_ok=True)
    return path
