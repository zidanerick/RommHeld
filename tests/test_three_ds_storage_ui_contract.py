from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]
LIBRARY_PATH = ROOT / "romm_vita_manager" / "three_ds_library.py"
DEPLOY_PATH = ROOT / "romm_vita_manager" / "three_ds_filesystem_deploy.py"
DASHBOARD_PATH = ROOT / "romm_vita_manager" / "workspace_dashboard.py"
SETUP_PATH = ROOT / "romm_vita_manager" / "three_ds_setup.py"


def test_3ds_filesystem_dialog_exposes_mounted_sd_and_ftpd_routes():
    source = DEPLOY_PATH.read_text(encoding="utf-8")

    assert "Mounted SD card · Direct / offline" in source
    assert "ftpd · Wireless / live console" in source
    assert "configured_3ds_storage_root" in source
    assert "ThreeDSMountedTransferWorker" in source
    assert 'transport not in {"sd", "ftp"}' in source


def test_3ds_package_generation_remains_separate_from_filesystem_transport():
    library = LIBRARY_PATH.read_text(encoding="utf-8")
    deploy = DEPLOY_PATH.read_text(encoding="utf-8")

    assert 'PACKAGE_GENERATION_TARGETS = frozenset({"native_gba", "vc_cia"})' in library
    assert "if target_key in PACKAGE_GENERATION_TARGETS:" in library
    assert "self.open_manager_callback(game, target_key)" in library
    assert "ThreeDSFilesystemDeployDialog(self.config, game, target_key, self).exec()" in library
    assert "PACKAGE_GENERATION_TARGETS" not in deploy


def test_3ds_ui_describes_direct_card_access_without_claiming_console_usb_storage():
    dashboard = DASHBOARD_PATH.read_text(encoding="utf-8")
    setup = SETUP_PATH.read_text(encoding="utf-8")
    deploy = DEPLOY_PATH.read_text(encoding="utf-8")

    assert "Nintendo 3DS systems do not expose a standard USB mass-storage mode" in dashboard
    assert "Mounted SD" in dashboard
    assert "direct/offline file access" in setup
    assert "card reader" in setup
    assert "card reader" in deploy
    assert "standard USB mass storage" in deploy
