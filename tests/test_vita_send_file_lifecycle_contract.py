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


def test_send_file_dialog_blocks_all_dismissal_paths_during_transfer():
    source = source_text()

    assert "def _worker_active(self) -> bool:" in source
    assert "return self.worker is not None and self.worker.isRunning()" in source
    assert "def accept(self) -> None:" in source
    assert "def reject(self) -> None:" in source
    assert "def closeEvent(self, event: QCloseEvent) -> None:" in source
    assert source.count("if self._worker_active():") >= 3
    assert "super().accept()" in source
    assert "super().reject()" in source
    assert "super().closeEvent(event)" in source


def test_send_file_revalidates_vita_usb_mount_before_writing():
    source = source_text()

    assert "from .vita import free_space, is_vita_mount" in source
    assert "self.vita = vita if vita is not None and is_vita_mount(vita) else None" in source
    assert "if self.vita is None or not is_vita_mount(self.vita):" in source
    assert "The VitaShell USB mount is no longer available." in source
