from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]
LIBRARY_PATH = ROOT / "romm_vita_manager" / "three_ds_library.py"
DEPLOY_PATH = ROOT / "romm_vita_manager" / "three_ds_filesystem_deploy.py"
DASHBOARD_PATH = ROOT / "romm_vita_manager" / "workspace_dashboard.py"
SETUP_PATH = ROOT / "romm_vita_manager" / "three_ds_setup.py"
GBA_DEPLOY_PATH = ROOT / "romm_vita_manager" / "gba_vc_deploy.py"
CLASSIC_DEPLOY_PATH = ROOT / "romm_vita_manager" / "classic_vc_deploy.py"


def test_3ds_filesystem_dialog_exposes_mounted_sd_and_ftpd_routes():
    source = DEPLOY_PATH.read_text(encoding="utf-8")

    assert "Mounted SD card · Direct / offline" in source
    assert "ftpd · Wireless / live console" in source
    assert "configured_3ds_storage_root" in source
    assert "ThreeDSMountedTransferWorker" in source
    assert 'transport not in {"sd", "ftp"}' in source


def test_3ds_filesystem_dialog_surfaces_runtime_readiness_without_blocking_transport():
    source = DEPLOY_PATH.read_text(encoding="utf-8")
    readiness = (ROOT / "romm_vita_manager" / "three_ds_readiness.py").read_text(
        encoding="utf-8"
    )

    assert "evaluate_target_runtime" in source
    assert 'StatusPill("Runtime", "Not checked")' in source
    assert "evaluate_target_runtime(root, self.target_key, self.platform_slug)" in source
    assert 'self.runtime_status.set_value("Detected")' in source
    assert 'self.runtime_status.set_value("Confirm on console")' in source
    assert 'self.runtime_status.set_value("Needs setup")' in source
    assert "The file can still be transferred with ftpd" in source
    assert "The ROM can still " in readiness
    assert "be copied now, but this route will not be launchable" in readiness
    assert "scan_retroarch_route" in readiness


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

    assert "Mounted SD is the fastest offline route" in dashboard
    assert "ftpd is the live-console wireless route" in dashboard
    assert "direct/offline file access" in setup
    assert "card reader" in setup
    assert "card reader" in deploy
    assert "standard USB mass storage" in deploy


def test_3ds_setup_does_not_treat_loose_installer_cias_as_app_detection():
    setup = SETUP_PATH.read_text(encoding="utf-8")

    assert '"FBI.cia"' not in setup
    assert '"Universal-Updater.cia"' not in setup
    assert "installed CIA title cannot be reliably inferred from SD files alone" in setup


def test_3ds_filesystem_dialog_preserves_transfer_result_after_worker_cleanup():
    source = DEPLOY_PATH.read_text(encoding="utf-8")

    assert "update_activity: bool = True" in source
    assert "if update_activity:" in source
    assert '"Transfer complete. The final destination was size verified."' in source
    assert '"Transfer cancelled. The existing destination was preserved."' in source
    assert "self.status.setText(prefix + message)" in source
    assert "self._transport_changed(update_activity=False)" in source


def test_generated_cia_workflows_offer_sd_copy_without_claiming_installation():
    for path in (GBA_DEPLOY_PATH, CLASSIC_DEPLOY_PATH):
        source = path.read_text(encoding="utf-8")
        assert "Mounted SD card · Copy CIA" in source
        assert "ftpd · Copy CIA" in source
        assert "FBI Remote Install · Install directly" in source
        assert "configured_3ds_storage_root" in source
        assert "ThreeDSMountedStorageBackend" in source
        assert 'self.install_method == "sd"' in source


def test_generated_cia_sd_copy_remains_post_install_manual():
    gba = GBA_DEPLOY_PATH.read_text(encoding="utf-8")
    classic = CLASSIC_DEPLOY_PATH.read_text(encoding="utf-8")

    assert "Install copied CIAs later with FBI" in gba
    assert "return it to the console, then install the CIA with FBI" in gba
    assert "return it to the console, then install the CIA with FBI" in classic
    assert "Install it later with FBI" in classic
