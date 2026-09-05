from pathlib import Path


SOURCE = Path("romm_vita_manager/workspace_dashboard.py")


def source_text() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_workspace_has_one_library_transfer_lifecycle_gate() -> None:
    source = source_text()

    assert "def _library_transfer_active(self) -> bool:" in source
    assert "worker = self.local_library.worker" in source
    assert "return worker is not None and worker.isRunning()" in source
    assert "def _block_for_library_transfer(self, action: str) -> bool:" in source
    assert 'f"Cancel the active Library transfer before {action}."' in source


def test_library_transfer_blocks_top_level_workspace_transitions() -> None:
    source = source_text()

    assert source.count("self._block_for_library_transfer(") >= 5
    assert 'self._block_for_library_transfer("resetting setup")' in source
    assert 'self._block_for_library_transfer("changing library settings")' in source
    assert 'self._block_for_library_transfer("switching handhelds")' in source
    assert 'self._block_for_library_transfer("opening Send file")' in source
    assert 'self._block_for_library_transfer("opening Vita Setup")' in source


def test_library_refresh_and_window_close_do_not_destroy_active_transfer() -> None:
    source = source_text()

    assert "if self._library_transfer_active():\n            return" in source
    assert '"Cancel the active Library transfer before closing RommHeld."' in source
    assert "event.ignore()" in source
