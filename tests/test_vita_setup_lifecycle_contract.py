from pathlib import Path


SOURCE = Path("romm_vita_manager/vita_setup.py")


def source_text() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_vita_setup_worker_uses_one_cancellation_event_for_package_io():
    source = source_text()

    assert "def cancel(self) -> None:" in source
    assert "self.cancel_event.set()" in source
    assert "download_package(" in source
    assert "cancel_event=self.cancel_event" in source
    assert "stage_package(" in source
    assert source.count("cancel_event=self.cancel_event") >= 3
    assert "except InterruptedError as exc:" in source
    assert "self.cancelled.emit(str(exc))" in source


def test_vita_setup_exposes_cancel_and_keeps_dialog_alive_during_worker():
    source = source_text()

    assert 'self.cancel_button = QPushButton("Cancel current action")' in source
    assert "self.cancel_button.clicked.connect(self._cancel_worker)" in source
    assert "self.worker.cancelled.connect(self._package_cancelled)" in source
    assert "self.worker.cancel()" in source
    assert "self.done_button.setEnabled(False)" in source
    assert "self.done_button.setEnabled(True)" in source
    assert "Cancel the current package action or allow it to finish before closing this window." in source
