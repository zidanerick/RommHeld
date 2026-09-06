from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_choice_controls_do_not_paint_app_background_inside_cards() -> None:
    theme = _source("romm_vita_manager/theme.py")

    assert "QRadioButton, QCheckBox" in theme
    choice_rule = theme.split("QRadioButton, QCheckBox", 1)[1].split("}", 1)[0]
    assert "background: transparent;" in choice_rule


def test_handheld_selector_cards_keep_visible_keyboard_focus() -> None:
    source = _source("romm_vita_manager/console_selector.py")

    assert "Qt.FocusPolicy.StrongFocus if self.selectable" in source
    assert "QFrame#consoleTile:focus" in source
    focus_rule = source.split("QFrame#consoleTile:focus", 1)[1].split("}", 1)[0]
    assert "border:2px solid {DARK.text_primary};" in focus_rule
    assert "Qt.Key.Key_Return" in source
    assert "Qt.Key.Key_Enter" in source
    assert "Qt.Key.Key_Space" in source


def test_management_shell_navigation_keeps_visible_keyboard_focus() -> None:
    source = _source("romm_vita_manager/management_shell.py")

    assert "QPushButton#navButton:focus" in source
    nav_focus_rule = source.split("QPushButton#navButton:focus", 1)[1].split("}", 1)[0]
    assert "border:1px solid {DARK.text_primary};" in nav_focus_rule

    assert "QPushButton#changeButton:focus" in source
    switch_focus_rule = source.split("QPushButton#changeButton:focus", 1)[1].split("}", 1)[0]
    assert "border-color:{DARK.text_primary};" in switch_focus_rule


def test_3ds_setup_scrolls_cards_instead_of_compressing_them() -> None:
    source = _source("romm_vita_manager/three_ds_setup.py")

    assert "QScrollArea" in source
    assert "QLayout.SizeConstraint.SetMinimumSize" in source
    assert "scroll.setWidgetResizable(True)" in source
    assert "scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)" in source
    assert "scroll_body_layout.addWidget(storage_card)" in source
    assert "scroll_body_layout.addWidget(ftp_card)" in source
    assert "scroll_body_layout.addWidget(fbi_card)" in source
    assert "scroll_body_layout.addWidget(runtime_card)" in source
    assert "layout.addWidget(scroll, 1)" in source
