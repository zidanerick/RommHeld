from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "romm_vita_manager" / "workspace_dashboard.py"


def _source() -> str:
    return WORKSPACE.read_text(encoding="utf-8")


def test_workspace_defers_transitions_while_3ds_library_workers_are_running():
    source = _source()
    assert "def _three_ds_library_workers" in source
    assert "def _block_for_three_ds_library_activity" in source
    assert 'requestInterruption()' in source
    assert '_block_for_three_ds_library_activity("switching handhelds")' in source
    assert '_block_for_three_ds_library_activity("changing library settings")' in source
    assert '_block_for_three_ds_library_activity("resetting setup")' in source
    assert '_block_for_three_ds_library_activity("closing RommHeld")' in source


def test_workspace_close_does_not_wait_on_network_threads():
    source = _source()
    close_event = source.split("    def closeEvent(self, event) -> None:", 1)[1]
    assert ".wait()" not in close_event
    assert "Finish the RomM connection test before closing RommHeld." in close_event


def test_workspace_rebuild_has_defensive_3ds_worker_guard():
    source = _source()
    rebuild = source.split("    def _rebuild_workspace_sections(self) -> bool:", 1)[1]
    rebuild = rebuild.split("    def _rebuild_workspace_tabs", 1)[0]
    assert '_block_for_three_ds_library_activity("rebuilding the workspace")' in rebuild
    assert "return False" in rebuild
