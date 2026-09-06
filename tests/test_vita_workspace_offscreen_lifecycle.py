from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from romm_vita_manager import local_library as local_library_module
from romm_vita_manager import workspace_dashboard as workspace_module
from romm_vita_manager.workspace_dashboard import WorkspaceDashboardWindow


_APP: QApplication | None = None


def _app() -> QApplication:
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
    return _APP


class _Worker:
    def __init__(self, running: bool = True) -> None:
        self.running = running

    def isRunning(self) -> bool:
        return self.running


def _unexpected(*_args, **_kwargs):
    raise AssertionError("guarded action reached a destructive/rebuilding boundary")


def test_active_vita_library_transfer_blocks_real_workspace_transitions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    library_root = tmp_path / "library"
    library_root.mkdir()
    config = {
        "setup_complete": True,
        "active_console": "vita",
        "library_source": {
            "mode": "local",
            "local_root": str(library_root),
        },
        "devices": {},
        "platform_mappings": {},
    }

    monkeypatch.setattr(workspace_module, "load_config", lambda: dict(config))
    monkeypatch.setattr(local_library_module, "load_config", lambda: dict(config))
    monkeypatch.setattr(local_library_module, "scan_games", lambda _root: [])
    monkeypatch.setattr(workspace_module, "find_vita_mounts", lambda: [])

    window = WorkspaceDashboardWindow(config)
    window.show()
    app.processEvents()

    worker = _Worker()
    window.local_library.worker = worker

    monkeypatch.setattr(workspace_module, "PlatformSelectorDialog", _unexpected)
    monkeypatch.setattr(workspace_module, "SendFileDialog", _unexpected)
    monkeypatch.setattr(workspace_module, "VitaSetupDialog", _unexpected)
    monkeypatch.setattr(workspace_module, "save_library_source", _unexpected)
    monkeypatch.setattr(workspace_module, "reset_config", _unexpected)
    monkeypatch.setattr(window.local_library, "refresh_library", _unexpected)

    window.change_workspace()
    assert "Cancel the active Library transfer before switching handhelds." in window.statusBar().currentMessage()

    window._save_settings_source()
    assert "Cancel the active Library transfer before changing library settings." in window.statusBar().currentMessage()

    window._reset_application_setup()
    assert "Cancel the active Library transfer before resetting setup." in window.statusBar().currentMessage()

    window.open_vita_send_file()
    assert "Cancel the active Library transfer before opening Send file." in window.statusBar().currentMessage()

    window.open_vita_setup()
    assert "Cancel the active Library transfer before opening Vita Setup." in window.statusBar().currentMessage()

    window.refresh_games()

    monkeypatch.setattr(workspace_module.QMessageBox, "information", lambda *_args, **_kwargs: None)
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()

    worker.running = False
    assert not window._library_transfer_active()

    window.local_library.worker = None
    window.close()
    window.deleteLater()
    app.processEvents()
