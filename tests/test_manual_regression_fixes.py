from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from romm_vita_manager import local_library as local_library_module
from romm_vita_manager import storage_detection as storage_detection_module
from romm_vita_manager import workspace_dashboard as workspace_dashboard_module
from romm_vita_manager.local_storage_ui import MountedStorageDialog
from romm_vita_manager.workspace_dashboard import WorkspaceDashboardWindow


_APP: QApplication | None = None


def _app() -> QApplication:
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
    return _APP


def test_settings_switch_from_local_to_romm_clears_local_status(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    config = {
        "active_console": "vita",
        "library_source": {
            "mode": "local",
            "local_root": str(tmp_path),
            "romm_url": "http://romm.example",
            "api_token": "token",
        },
        "devices": {},
    }
    monkeypatch.setattr(workspace_dashboard_module, "load_config", lambda: dict(config))
    monkeypatch.setattr(local_library_module, "load_config", lambda: dict(config))
    monkeypatch.setattr(local_library_module, "scan_games", lambda _root: [])
    monkeypatch.setattr(
        WorkspaceDashboardWindow,
        "_safe_vita_mounts",
        staticmethod(lambda: []),
    )

    window = WorkspaceDashboardWindow(config)
    window.shell.select_section("settings")
    app.processEvents()

    assert window.settings_source_status.text() == "Local library ready"
    window.settings_romm_radio.setChecked(True)
    app.processEvents()

    assert (
        window.settings_source_status.text()
        == "Test the RomM connection before saving if these credentials changed."
    )

    window._set_settings_source_state("error", "RomM unavailable • test failure")
    window._settings_source_visibility()
    assert window.settings_source_status.text() == "RomM unavailable • test failure"

    window.close()
    window.deleteLater()
    app.processEvents()


def test_3ds_sd_detection_rejects_generic_rom_library(
    tmp_path: Path,
    monkeypatch,
) -> None:
    generic = tmp_path / "rom-library"
    (generic / "roms").mkdir(parents=True)
    (generic / "3ds").mkdir()

    monkeypatch.setattr(
        storage_detection_module,
        "writable_volumes",
        lambda: [generic],
    )
    monkeypatch.setattr(
        storage_detection_module,
        "volume_info",
        lambda _root: {},
    )

    assert storage_detection_module.detect_3ds_sd_candidates() == []


def test_3ds_sd_detection_keeps_medium_or_high_confidence_media(
    tmp_path: Path,
    monkeypatch,
) -> None:
    card = tmp_path / "NINTENDO3DS"
    card.mkdir()
    (card / "boot.firm").write_bytes(b"firm")
    (card / "boot.3dsx").write_bytes(b"3dsx")
    (card / "luma").mkdir()

    monkeypatch.setattr(
        storage_detection_module,
        "writable_volumes",
        lambda: [card],
    )
    monkeypatch.setattr(
        storage_detection_module,
        "volume_info",
        lambda _root: {"display_name": "NINTENDO3DS", "filesystem": "vfat"},
    )

    candidates = storage_detection_module.detect_3ds_sd_candidates()
    assert len(candidates) == 1
    assert candidates[0].root == card
    assert candidates[0].validation.confidence == "high"


def test_mounted_storage_status_reserves_space_below_root_controls() -> None:
    app = _app()
    dialog = MountedStorageDialog(
        {"devices": {"3ds": {"storage_root": "/definitely/missing/NINTENDO3DS"}}},
        "3ds",
        "Nintendo 3DS",
    )
    dialog.resize(840, 590)
    dialog.show()
    app.processEvents()

    root_bottom = dialog.root_edit.mapTo(
        dialog,
        QPoint(0, dialog.root_edit.height()),
    ).y()
    status_top = dialog.storage_status.mapTo(dialog, QPoint(0, 0)).y()

    assert dialog.storage_status.minimumHeight() >= 40
    assert status_top >= root_bottom

    dialog.close()
    dialog.deleteLater()
    app.processEvents()
