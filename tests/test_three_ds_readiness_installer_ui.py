from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from romm_vita_manager.three_ds_readiness_ui import ThreeDSReadinessDialog


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

    _select(dialog, "daedalusx64")
    assert dialog.stage_button.isEnabled()
    assert dialog.stage_button.text() == "Prepare Universal-Updater"

    _select(dialog, "luma")
    assert not dialog.stage_button.isEnabled()
    assert dialog.stage_button.text() == "No automatic install"

    _select(dialog, "dsp-firmware")
    assert not dialog.stage_button.isEnabled()
    assert dialog.stage_button.text() == "Generate on console"

    dialog.close()
    app.processEvents()


def test_complex_app_switches_to_updater_steps_when_updater_is_present(tmp_path: Path) -> None:
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

    _select(dialog, "daedalusx64")
    assert dialog.stage_button.isEnabled()
    assert dialog.stage_button.text() == "Show updater steps"
    assert "launch Universal-Updater on the 3DS" in dialog.detail_text.text()
    assert "search for DaedalusX64" in dialog.detail_text.text()

    dialog.close()
    app.processEvents()
