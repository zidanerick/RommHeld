from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_NAME = "RommHeld"
LEGACY_CONFIG_PATH = Path.home() / ".config" / "romm-vita-manager" / "config.json"


def app_config_dir() -> Path:
    """Return a platform-appropriate per-user configuration directory."""
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return root / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return root / APP_NAME.lower()


APP_DIR = app_config_dir()
CONFIG_PATH = APP_DIR / "config.json"
DEFAULT_ROMM_ROOT = Path.home() / "RomM" / "roms" / "roms"


def load_config() -> dict:
    paths = (CONFIG_PATH, LEGACY_CONFIG_PATH)
    for path in paths:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                return value
        except (OSError, json.JSONDecodeError):
            continue
    return {}


def save_config(config: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, indent=2), encoding="utf-8")
    temporary.replace(CONFIG_PATH)
