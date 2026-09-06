from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from romm_vita_manager import send_file_dialog as send_file_module
from romm_vita_manager import vita_setup as vita_setup_module
from romm_vita_manager.send_file_dialog import SendFileDialog
from romm_vita_manager.vita_setup import VitaSetupDialog


_APP: QApplication | None = None


def app() -> QApplication:
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
    return _APP


class RunningWorker:
    def __init__(self) -> None:
        self.running = True

    def isRunning(self) -> bool:
        return self.running


def empty_config() -> dict:
    return {
        "devices": {},
        "platform_mappings": {},
    }


def test_send_file_dialog_blocks_accept_reject_and_close_until_worker_finishes(monkeypatch) -> None:
    qt_app = app()
    monkeypatch.setattr(send_file_module, "load_config", empty_config)
    monkeypatch.setattr(send_file_module.QMessageBox, "information", lambda *_args, **_kwargs: None)
    dialog = SendFileDialog(None)
    worker = RunningWorker()
    dialog.worker = worker
    dialog.show()
    qt_app.processEvents()

    dialog.accept()
    qt_app.processEvents()
    assert dialog.isVisible()

    dialog.reject()
    qt_app.processEvents()
    assert dialog.isVisible()

    dialog.close()
    qt_app.processEvents()
    assert dialog.isVisible()

    worker.running = False
    dialog.accept()
    qt_app.processEvents()
    assert not dialog.isVisible()

    dialog.deleteLater()
    qt_app.processEvents()


def test_vita_setup_dialog_blocks_accept_reject_and_close_until_worker_finishes(monkeypatch) -> None:
    qt_app = app()
    monkeypatch.setattr(vita_setup_module, "load_config", empty_config)
    monkeypatch.setattr(vita_setup_module.QMessageBox, "information", lambda *_args, **_kwargs: None)
    dialog = VitaSetupDialog(None)
    worker = RunningWorker()
    dialog.worker = worker
    dialog.show()
    qt_app.processEvents()

    dialog.accept()
    qt_app.processEvents()
    assert dialog.isVisible()

    dialog.reject()
    qt_app.processEvents()
    assert dialog.isVisible()

    dialog.close()
    qt_app.processEvents()
    assert dialog.isVisible()

    worker.running = False
    dialog.reject()
    qt_app.processEvents()
    assert not dialog.isVisible()

    dialog.deleteLater()
    qt_app.processEvents()
