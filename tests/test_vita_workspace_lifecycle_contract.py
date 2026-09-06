from pathlib import Path
from types import SimpleNamespace

from romm_vita_manager.workspace_dashboard import WorkspaceDashboardWindow


SOURCE = Path("romm_vita_manager/workspace_dashboard.py")


def source_text() -> str:
    return SOURCE.read_text(encoding="utf-8")


class _Worker:
    def __init__(self, running: bool) -> None:
        self.running = running

    def isRunning(self) -> bool:
        return self.running


class _WindowHarness:
    _library_transfer_active = WorkspaceDashboardWindow._library_transfer_active
    _block_for_library_transfer = WorkspaceDashboardWindow._block_for_library_transfer

    def __init__(self, running: bool) -> None:
        self.local_library = SimpleNamespace(worker=_Worker(running))
        self.messages: list[tuple[str, int]] = []

    def statusBar(self):
        return self

    def showMessage(self, message: str, timeout: int) -> None:
        self.messages.append((message, timeout))


def test_workspace_has_one_library_transfer_lifecycle_gate() -> None:
    source = source_text()

    assert "def _library_transfer_active(self) -> bool:" in source
    assert "worker = self.local_library.worker" in source
    assert "return worker is not None and worker.isRunning()" in source
    assert "def _block_for_library_transfer(self, action: str) -> bool:" in source
    assert 'f"Cancel the active Library transfer before {action}."' in source


def test_library_transfer_gate_reports_active_worker_and_blocks_action() -> None:
    window = _WindowHarness(running=True)

    assert window._library_transfer_active()
    assert window._block_for_library_transfer("switching handhelds")
    assert window.messages == [
        ("Cancel the active Library transfer before switching handhelds.", 5000)
    ]


def test_library_transfer_gate_allows_action_after_worker_finishes() -> None:
    window = _WindowHarness(running=False)

    assert not window._library_transfer_active()
    assert not window._block_for_library_transfer("switching handhelds")
    assert window.messages == []


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
