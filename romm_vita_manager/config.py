from __future__ import annotations

import json
from pathlib import Path

APP_DIR = Path.home() / ".config" / "romm-vita-manager"
CONFIG_PATH = APP_DIR / "config.json"
DEFAULT_ROMM_ROOT = Path.home() / "RomM" / "roms" / "roms"


def load_config() -> dict:
    try:
        value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(config: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, indent=2), encoding="utf-8")
    temporary.replace(CONFIG_PATH)
