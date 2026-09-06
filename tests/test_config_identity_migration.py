from __future__ import annotations

import json
from pathlib import Path

from romm_vita_manager import config as config_module


def _redirect_config_paths(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    stable = tmp_path / "RommHeld" / "config.json"
    unscoped = tmp_path / "config.json"
    old_named = tmp_path / "romm-vita-manager" / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_PATH", stable)
    monkeypatch.setattr(config_module, "APP_DIR", stable.parent)
    monkeypatch.setattr(config_module, "LEGACY_UNSCOPED_CONFIG_PATH", unscoped)
    monkeypatch.setattr(config_module, "LEGACY_CONFIG_PATH", old_named)
    return stable, unscoped, old_named


def test_recognisable_pre_identity_config_migrates_to_stable_app_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    stable, unscoped, _old_named = _redirect_config_paths(monkeypatch, tmp_path)
    legacy = {
        "setup_complete": True,
        "active_console": "vita",
        "library_source": {"mode": "local", "local_root": "/example/library"},
    }
    unscoped.write_text(json.dumps(legacy), encoding="utf-8")

    loaded = config_module.load_config()

    assert loaded == legacy
    assert json.loads(stable.read_text(encoding="utf-8")) == legacy


def test_unrelated_generic_config_is_not_claimed_as_rommheld_data(
    monkeypatch,
    tmp_path: Path,
) -> None:
    stable, unscoped, _old_named = _redirect_config_paths(monkeypatch, tmp_path)
    unscoped.write_text(json.dumps({"unrelated_application": True}), encoding="utf-8")

    assert config_module.load_config() == {}
    assert not stable.exists()


def test_existing_stable_config_wins_over_both_legacy_locations(
    monkeypatch,
    tmp_path: Path,
) -> None:
    stable, unscoped, old_named = _redirect_config_paths(monkeypatch, tmp_path)
    stable.parent.mkdir(parents=True)
    old_named.parent.mkdir(parents=True)
    current = {"setup_complete": True, "active_console": "3ds"}
    stable.write_text(json.dumps(current), encoding="utf-8")
    unscoped.write_text(
        json.dumps({"setup_complete": True, "active_console": "vita"}),
        encoding="utf-8",
    )
    old_named.write_text(
        json.dumps({"setup_complete": True, "active_console": "ds"}),
        encoding="utf-8",
    )

    assert config_module.load_config() == current
