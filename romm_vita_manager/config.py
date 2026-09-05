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


def _preserve_independent_device_fields(config: dict) -> dict:
    """Preserve separately owned device settings omitted by focused editors.

    The 3DS FTP manager historically replaces its own `devices.3ds` mapping.
    Mounted-SD state is an independent transport setting, so an FTP-only save
    must not erase it. Explicitly supplying `storage_root` still changes or
    clears the value normally.
    """
    existing = _load_path(CONFIG_PATH)
    existing_3ds = existing.get("devices", {}).get("3ds", {})
    old_root = existing_3ds.get("storage_root") if isinstance(existing_3ds, dict) else None
    if old_root is None:
        return config

    devices = config.get("devices")
    if not isinstance(devices, dict):
        return config
    three_ds = devices.get("3ds")
    if not isinstance(three_ds, dict) or "storage_root" in three_ds:
        return config

    updated = dict(config)
    updated_devices = dict(devices)
    updated_3ds = dict(three_ds)
    updated_3ds["storage_root"] = old_root
    updated_devices["3ds"] = updated_3ds
    updated["devices"] = updated_devices
    return updated


def save_config(config: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    config = _preserve_independent_device_fields(config)
    temporary = CONFIG_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, indent=2), encoding="utf-8")
    temporary.replace(CONFIG_PATH)


def package_cache_dir() -> Path:
    path = cache_dir() / "packages"
    path.mkdir(parents=True, exist_ok=True)
    return path
