from pathlib import Path


SOURCE = Path("romm_vita_manager/local_library.py")


def test_usb_planner_does_not_requeue_already_complete_vita_destinations() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'if state in {"INSTALLED", "STAGED"}:' in source


def test_staged_vpk_state_is_visible_and_filterable_in_the_library() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert '"STAGED": "Staged for install"' in source
    assert '"Staged for install",' in source
    assert 'if wanted == "Staged for install" and state != "STAGED":' in source


def test_copy_action_requires_at_least_one_safe_destination_mapping() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'def _safe_destination_count(self, selected: list[Game]) -> int:' in source
    assert 'if mode != "unknown" and destination:' in source
    assert 'and safe_destination_count > 0' in source
    assert 'Selected games need destination review before they can be copied.' in source
    assert 'if mode == "unknown" or not target:' in source


def test_usb_copy_revalidates_cached_vita_mount_before_planning() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "from .vita import free_space, is_vita_mount" in source
    assert "if self.vita is None or not is_vita_mount(self.vita):" in source
    assert "self.set_vita(None)" in source
    assert "The VitaShell USB mount is no longer available." in source
