from __future__ import annotations

import json
from pathlib import Path

from romm_vita_manager import config as config_module


def _redirect_config(monkeypatch, tmp_path: Path) -> Path:
    stable = tmp_path / "RommHeld" / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_PATH", stable)
    monkeypatch.setattr(config_module, "APP_DIR", stable.parent)
    monkeypatch.setattr(config_module, "LEGACY_UNSCOPED_CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(
        config_module,
        "LEGACY_CONFIG_PATH",
        tmp_path / "romm-vita-manager" / "config.json",
    )
    return stable


def test_reset_preserves_all_vc_identity_and_prepared_cache_metadata(monkeypatch, tmp_path: Path):
    stable = _redirect_config(monkeypatch, tmp_path)
    stable.parent.mkdir(parents=True)
    existing = {
        "setup_complete": True,
        "active_console": "3ds",
        "library_source": {"mode": "romm_api"},
        "three_ds_vc": {"title_id_allocations": {"gb:source:1": "000400000e123400"}},
        "gba_vc": {"boot_logo_path": "/cache/agb_firm_boot_logo.bin"},
        "classic_vc": {
            "nes": {
                "cache_version": 5,
                "runtime_profile": {"profile_id": "runtime-profile"},
            }
        },
    }
    stable.write_text(json.dumps(existing), encoding="utf-8")

    reset = config_module.reset_config()

    assert reset == {
        "setup_complete": False,
        "three_ds_vc": existing["three_ds_vc"],
        "gba_vc": existing["gba_vc"],
        "classic_vc": existing["classic_vc"],
    }
    assert json.loads(stable.read_text(encoding="utf-8")) == reset


def test_pre_identity_migration_recognises_classic_vc_only_config(monkeypatch, tmp_path: Path):
    stable = _redirect_config(monkeypatch, tmp_path)
    legacy = {
        "classic_vc": {
            "gbc": {
                "cache_version": 5,
                "runtime_profile": {"profile_id": "gbc-profile"},
            }
        }
    }
    config_module.LEGACY_UNSCOPED_CONFIG_PATH.write_text(
        json.dumps(legacy),
        encoding="utf-8",
    )

    assert config_module.load_config() == legacy
    assert json.loads(stable.read_text(encoding="utf-8")) == legacy
