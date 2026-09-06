from pathlib import Path

from romm_vita_manager import config as config_module


ROOT = Path(__file__).resolve().parents[1]


def test_reset_config_clears_setup_but_preserves_vc_identity(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config_module, "APP_DIR", tmp_path)
    monkeypatch.setattr(config_module, "LEGACY_CONFIG_PATH", tmp_path / "legacy.json")

    original = {
        "setup_complete": True,
        "active_console": "3ds",
        "library_source": {"mode": "romm_api", "romm_url": "https://example.invalid"},
        "devices": {"3ds": {"host": "192.0.2.1", "storage_root": "/media/3ds"}},
        "runtime_preferences": {"3ds": "retroachievements"},
        "three_ds_vc": {
            "title_id_allocations": {"nes:default:1": "000400000e000000"},
            "donors": {"nes": {"title_id": "0004000000000000"}},
        },
        "gba_vc": {"boot_logo_path": "/cache/agb_firm_boot_logo.bin"},
    }
    config_module.save_config(original)

    reset = config_module.reset_config()

    assert reset["setup_complete"] is False
    assert reset["three_ds_vc"] == original["three_ds_vc"]
    assert reset["gba_vc"] == original["gba_vc"]
    assert "active_console" not in reset
    assert "library_source" not in reset
    assert "devices" not in reset
    assert "runtime_preferences" not in reset
    assert config_module.load_config() == reset


def test_settings_exposes_confirmed_application_setup_reset() -> None:
    source = (ROOT / "romm_vita_manager" / "workspace_dashboard.py").read_text(
        encoding="utf-8"
    )

    assert 'reset_button = QPushButton("Reset setup")' in source
    assert "reset_button.clicked.connect(self._reset_application_setup)" in source
    assert "def _reset_application_setup(self) -> None:" in source
    assert 'confirm.addButton("Reset setup", QMessageBox.ButtonRole.DestructiveRole)' in source
    assert 'confirm.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)' in source
    assert "confirm.clickedButton() is not reset_button" in source
    assert "self.config = reset_config()" in source
    assert "PlatformSelectorDialog(self.config, self)" in source
    assert "Virtual Console donor caches and generated Title ID allocations will be kept." in source
