from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from romm_vita_manager.ftp_file_manager_ui import FtpFileManagerDialog
from romm_vita_manager.three_ds_ftp import ThreeDSFtpSettings
from romm_vita_manager.vita_ftp import VitaFtpSettings


def _app():
    return QApplication.instance() or QApplication([])


def _dialog(monkeypatch, console, settings):
    _app()
    monkeypatch.setattr(FtpFileManagerDialog, "refresh_directory", lambda self: None)
    return FtpFileManagerDialog(console, settings)


def test_dialog_uses_console_specific_free_space_wording(monkeypatch):
    three_ds = _dialog(monkeypatch, "3ds", ThreeDSFtpSettings("192.0.2.3"))
    assert "checking" in three_ds.space_label.text().lower()
    assert three_ds.windowTitle() == "Nintendo 3DS FTP Files"
    three_ds.close()

    vita = _dialog(monkeypatch, "PlayStation TV", VitaFtpSettings("192.0.2.4"))
    assert "unavailable over VitaShell FTP" in vita.space_label.text()
    assert vita.windowTitle() == "PlayStation Vita FTP Files"
    vita.close()


def test_dialog_exposes_advanced_file_actions_without_recursive_delete(monkeypatch):
    dialog = _dialog(monkeypatch, "3ds", ThreeDSFtpSettings("192.0.2.3"))

    assert dialog.upload_button.text() == "Upload file"
    assert dialog.download_button.text() == "Download"
    assert dialog.new_folder_button.text() == "New folder"
    assert dialog.rename_button.text() == "Rename"
    assert dialog.delete_button.text() == "Delete"
    assert not hasattr(dialog, "delete_tree")
    assert not hasattr(dialog, "recursive_delete")
    dialog.close()


def test_sensitive_3ds_path_requires_stronger_confirmation(monkeypatch):
    dialog = _dialog(monkeypatch, "3ds", ThreeDSFtpSettings("192.0.2.3"))
    captured = {}

    def warning(parent, title, message, *args):
        captured["title"] = title
        captured["message"] = message
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "warning", warning)

    assert not dialog._confirm_sensitive_change("Nintendo 3DS/id0/id1/title", "Delete")
    assert "Sensitive Nintendo 3DS path" in captured["title"]
    assert "console-sensitive location" in captured["message"]
    dialog.close()


def test_different_size_upload_waits_for_first_worker_to_finish(monkeypatch, tmp_path: Path):
    dialog = _dialog(monkeypatch, "3ds", ThreeDSFtpSettings("192.0.2.3"))
    source = tmp_path / "game.bin"
    source.write_bytes(b"new")
    dialog._pending_upload = (source, "roms/game.bin")

    class FakeWorker:
        operation = "upload"

        def __init__(self):
            self.deleted = False

        def isRunning(self):
            return False

        def deleteLater(self):
            self.deleted = True

    original_worker = FakeWorker()
    dialog.worker = original_worker
    starts = []

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        dialog,
        "_start_worker",
        lambda operation, **kwargs: starts.append((operation, kwargs)),
    )

    dialog._operation_completed("upload", {"result": "different", "size": 0})

    assert dialog.worker is original_worker
    assert dialog._retry_upload_after_finish
    assert starts == []

    dialog._worker_finished()

    assert dialog.worker is None
    assert original_worker.deleted
    assert starts == [
        (
            "upload",
            {
                "remote_path": "roms/game.bin",
                "local_path": source,
                "overwrite": True,
                "transfer": True,
            },
        )
    ]
    dialog.close()


def test_close_requests_cancel_before_dialog_can_disappear(monkeypatch):
    dialog = _dialog(monkeypatch, "vita", VitaFtpSettings("192.0.2.4"))

    class FakeWorker:
        def __init__(self):
            self.cancelled = False

        def isRunning(self):
            return True

        def cancel(self):
            self.cancelled = True

    class FakeEvent:
        def __init__(self):
            self.ignored = False

        def ignore(self):
            self.ignored = True

    worker = FakeWorker()
    event = FakeEvent()
    dialog.worker = worker

    dialog.closeEvent(event)

    assert worker.cancelled
    assert event.ignored
    assert dialog._closing_requested

    dialog.worker = None
    dialog.close()
