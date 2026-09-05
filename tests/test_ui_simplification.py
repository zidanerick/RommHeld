from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_placeholder_navigation_is_not_exposed() -> None:
    source = _source("romm_vita_manager/management_shell.py")

    assert 'if key in {"queue", "tools"}:' in source
    assert 'device_heading = QLabel("DEVICE")' in source
    assert 'QPushButton("Switch handheld")' in source


def test_page_subtitles_are_contextual() -> None:
    source = _source("romm_vita_manager/management_shell.py")

    assert 'if section == "library":' in source
    assert 'if section == "device":' in source
    assert 'if section == "setup":' in source
    assert 'if section == "settings":' in source
    assert 'self.page_subtitle.setText(self._subtitle_for_section(key))' in source


def test_vita_copy_primary_action_lives_with_library_selection() -> None:
    source = _source("romm_vita_manager/local_library.py")

    assert 'self.copy_button = AccentButton(' in source
    assert '"Copy to Vita"' in source
    assert 'self.copy_button.clicked.connect(self.copy_selected)' in source
    assert 'self.transfer_status.setText(f"Transfer complete' in source
