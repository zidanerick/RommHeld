from __future__ import annotations

import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from romm_vita_manager.three_ds_apps import APP_BY_KEY, ThreeDSAppStatus
from romm_vita_manager.three_ds_ftp import ThreeDSFtpSettings
import romm_vita_manager.three_ds_readiness_ui as readiness_ui
from romm_vita_manager.three_ds_readiness_ui import ThreeDSReadinessDialog


ASSISTED_APPS = (
    "daedalusx64",
    "twilight",
    "retroarch",
    "godmode9",
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _high_confidence_3ds_root(root: Path) -> None:
    (root / "boot.firm").write_bytes(b"firm")
    (root / "boot.3dsx").write_bytes(b"3dsx")
    (root / "luma").mkdir()


def _select(dialog: ThreeDSReadinessDialog, app_key: str) -> None:
    for row in range(dialog.component_list.count()):
        item = dialog.component_list.item(row)
        if item.data(Qt.ItemDataRole.UserRole) == app_key:
            dialog.component_list.setCurrentRow(row)
            _app().processEvents()
            return
    raise AssertionError(f"Readiness component not found: {app_key}")


def _wait_until(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    app = _app()
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(0.005)
    app.processEvents()
    assert predicate()


def test_readiness_installer_actions_match_package_safety_boundary(tmp_path: Path) -> None:
    app = _app()
    sd_root = tmp_path / "sd"
    sd_root.mkdir()
    _high_confidence_3ds_root(sd_root)

    dialog = ThreeDSReadinessDialog(sd_root, needs_ftp=False)
    dialog.show()
    app.processEvents()

    _select(dialog, "checkpoint")
    assert dialog.stage_button.isEnabled()
    assert dialog.stage_button.text() == "Prepare Checkpoint"

    _select(dialog, "fbi")
    assert dialog.stage_button.isEnabled()
    assert dialog.stage_button.text() == "Prepare FBI"

    for app_key in ASSISTED_APPS:
        _select(dialog, app_key)
        assert dialog.stage_button.isEnabled()
        assert dialog.stage_button.text() == "Prepare Universal-Updater"
        assert f"search for {APP_BY_KEY[app_key].name}" in dialog.detail_text.text()

    _select(dialog, "open-agb-firm")
    assert not dialog.stage_button.isEnabled()
    assert dialog.stage_button.text() == "No automatic install"
    assert "Universal-Updater is currently not recommended" in dialog.detail_text.text()

    _select(dialog, "luma")
    assert not dialog.stage_button.isEnabled()
    assert dialog.stage_button.text() == "No automatic install"

    _select(dialog, "homebrew-launcher")
    assert not dialog.stage_button.isEnabled()
    assert dialog.stage_button.text() == "No automatic install"

    _select(dialog, "dsp-firmware")
    assert not dialog.stage_button.isEnabled()
    assert dialog.stage_button.text() == "Generate on console"

    dialog.close()
    app.processEvents()


def test_complex_apps_switch_to_updater_steps_when_updater_is_present(tmp_path: Path) -> None:
    app = _app()
    sd_root = tmp_path / "sd"
    sd_root.mkdir()
    _high_confidence_3ds_root(sd_root)
    updater = sd_root / "3ds" / "Universal-Updater"
    updater.mkdir(parents=True)
    (updater / "Universal-Updater.3dsx").write_bytes(b"updater")

    dialog = ThreeDSReadinessDialog(sd_root, needs_ftp=False)
    dialog.show()
    app.processEvents()

    for app_key in ASSISTED_APPS:
        _select(dialog, app_key)
        app_name = APP_BY_KEY[app_key].name
        assert dialog.stage_button.isEnabled()
        assert dialog.stage_button.text() == "Show updater steps"
        assert "launch Universal-Updater on the 3DS" in dialog.detail_text.text()
        assert f"search for {app_name}" in dialog.detail_text.text()

    _select(dialog, "open-agb-firm")
    assert not dialog.stage_button.isEnabled()
    assert dialog.stage_button.text() == "No automatic install"

    dialog.close()
    app.processEvents()


def test_ftp_only_readiness_uses_remote_inventory_without_requiring_sd(monkeypatch) -> None:
    app = _app()

    def fake_scan(settings, *, cancelled=None, **_kwargs):
        assert settings.host == "192.0.2.3"
        statuses = {
            definition.key: ThreeDSAppStatus(definition, False, source="ftp")
            for definition in readiness_ui.THREE_DS_APPS
        }
        statuses["ftpd"] = ThreeDSAppStatus(
            APP_BY_KEY["ftpd"], True, "live ftpd connection", source="ftp_live"
        )
        statuses["universal-updater"] = ThreeDSAppStatus(
            APP_BY_KEY["universal-updater"],
            True,
            "3ds/Universal-Updater/Universal-Updater.3dsx",
            source="ftp",
        )
        statuses["daedalusx64"] = ThreeDSAppStatus(
            APP_BY_KEY["daedalusx64"],
            True,
            "3ds/DaedalusX64/DaedalusX64.3dsx",
            source="ftp",
        )
        return statuses

    monkeypatch.setattr(readiness_ui, "scan_three_ds_apps_ftp", fake_scan)
    dialog = ThreeDSReadinessDialog(
        None,
        ftp_settings=ThreeDSFtpSettings("192.0.2.3"),
        needs_ftp=True,
    )
    dialog.show()

    _wait_until(lambda: dialog.ftp_scan_worker is None)
    assert "Live FTP: ftp://192.0.2.3:5000" in dialog.sd_label.text()

    _select(dialog, "ftpd")
    assert "Detected" in dialog.detail_title.text()
    assert "live ftpd connection" in dialog.detail_text.text().lower()

    _select(dialog, "daedalusx64")
    assert "Detected" in dialog.detail_title.text()
    assert "Live FTP evidence" in dialog.detail_text.text()
    assert dialog.stage_button.isEnabled()
    assert dialog.stage_button.text() == "Show updater steps"

    _select(dialog, "checkpoint")
    assert not dialog.stage_button.isEnabled()
    assert dialog.stage_button.text() == "Mount SD to prepare"

    dialog.close()
    app.processEvents()


def test_close_waits_for_ftp_readiness_worker_without_destroying_thread(monkeypatch) -> None:
    app = _app()

    def cancellable_scan(_settings, *, cancelled=None, **_kwargs):
        while cancelled is None or not cancelled():
            time.sleep(0.005)
        raise InterruptedError("cancelled")

    monkeypatch.setattr(readiness_ui, "scan_three_ds_apps_ftp", cancellable_scan)
    dialog = ThreeDSReadinessDialog(
        None,
        ftp_settings=ThreeDSFtpSettings("192.0.2.3"),
        needs_ftp=True,
    )
    dialog.show()
    _wait_until(
        lambda: dialog.ftp_scan_worker is not None
        and dialog.ftp_scan_worker.isRunning()
    )

    dialog.close()
    app.processEvents()
    assert dialog.isVisible()
    assert dialog.ftp_scan_worker is not None

    _wait_until(lambda: dialog.ftp_scan_worker is None and not dialog.isVisible())
