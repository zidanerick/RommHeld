from pathlib import Path


SOURCE = Path("romm_vita_manager/send_file_dialog.py")


def source_text() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_overwrite_retry_waits_for_previous_qthread_to_finish():
    source = source_text()

    assert "self._pending_overwrite_retry = True" in source
    assert "self.worker.finished.connect(self._worker_finished)" in source
    assert "def _worker_finished(self) -> None:" in source
    assert "retry = self._pending_overwrite_retry" in source
    assert "self.worker = None" in source
    assert "if retry:\n            self.start_transfer()" in source
    assert "self.overwrite = True\n                self._pending_overwrite_retry = True" in source


def test_send_file_dialog_cannot_accept_while_transfer_thread_is_active():
    source = source_text()

    assert 'self.done_button = QPushButton("Done")' in source
    assert "self.done_button.setEnabled(False)" in source
    assert "self.done_button.setEnabled(True)" in source
    assert "self._set_transfer_inputs_enabled(False)" in source
    assert "self._set_transfer_inputs_enabled(True)" in source
