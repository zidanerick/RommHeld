from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QWidget

from romm_vita_manager import local_library as local_library_module
from romm_vita_manager.local_library import LocalLibraryWidget
from romm_vita_manager.management_shell import ManagementShell, WORKSPACE_PROFILES
from romm_vita_manager.models import Game
from romm_vita_manager.theme import apply_application_theme


_APP: QApplication | None = None


def _app() -> QApplication:
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
        apply_application_theme(_APP)
    return _APP


def _assert_widget_inside(parent: QWidget, child: QWidget) -> None:
    top_left = child.mapTo(parent, QPoint(0, 0))
    bottom_right = child.mapTo(parent, QPoint(child.width() - 1, child.height() - 1))
    assert parent.rect().contains(top_left), (child.objectName(), top_left, parent.size())
    assert parent.rect().contains(bottom_right), (
        child.objectName(),
        bottom_right,
        parent.size(),
    )


def test_management_shell_renders_core_navigation_at_compact_desktop_size() -> None:
    app = _app()
    shell = ManagementShell(WORKSPACE_PROFILES["vita"])
    pages = {name: QWidget() for name in ("Library", "Device", "Settings")}
    for name, page in pages.items():
        shell.add_section(name, page)

    shell.resize(1024, 640)
    shell.show()
    app.processEvents()

    assert shell.size().width() == 1024
    assert shell.sidebar.width() == 238
    assert shell.content_root.width() > 600
    assert tuple(shell._sections) == ("library", "device", "settings")
    assert shell._device_widgets["vita"].isVisible()
    assert not shell._device_widgets["3ds"].isVisible()
    assert not shell._device_widgets["ds"].isVisible()

    for key, (button, page, display) in shell._sections.items():
        assert button.isVisible(), key
        assert button.width() > 150
        shell.select_section(key)
        app.processEvents()
        assert shell.stack.currentWidget() is page
        assert shell.page_title.text() == display
        assert shell.page_subtitle.text().strip()

    _assert_widget_inside(shell, shell.sidebar)
    _assert_widget_inside(shell, shell.content_root)
    shell.close()
    shell.deleteLater()
    app.processEvents()


def test_local_library_keeps_long_content_and_primary_action_in_bounds(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    library_root = tmp_path / "library with a deliberately long folder name"
    library_root.mkdir()
    vita_root = tmp_path / "vita"
    vita_root.mkdir()

    games = [
        Game(
            path=library_root / f"game-{index}.vpk",
            name=(
                "An Extremely Long PlayStation Vita Game Title Intended To Exercise "
                "Realistic Desktop Layout Without Hiding The Primary Action "
                f"{index}"
            ),
            source_platform="psvita",
            size=128 * 1024 * 1024 + index,
            relative=Path(f"game-{index}.vpk"),
        )
        for index in range(40)
    ]

    monkeypatch.setattr(local_library_module, "load_config", lambda: {"devices": {}})
    monkeypatch.setattr(local_library_module, "scan_games", lambda _root: list(games))
    monkeypatch.setattr(
        local_library_module,
        "destination_for_game",
        lambda root, game, _mappings: (
            "ux0:/data/RommHeld",
            Path(root) / "data" / "RommHeld" / game.relative,
            "mapped",
        ),
    )

    widget = LocalLibraryWidget(
        {
            "library_source": {"mode": "local", "local_root": str(library_root)},
            "platform_mappings": {},
        },
        "vita",
        vita_root,
    )
    widget.resize(760, 540)
    widget.show()
    app.processEvents()

    assert widget.width() == 760
    assert widget.game_list.count() == len(games)
    assert widget.search.width() >= 250
    assert widget.status_filter.isVisible()
    assert widget.vita_transport.isVisible()
    assert widget.copy_button.isVisible()

    for control in (
        widget.search,
        widget.refresh_button,
        widget.platforms,
        widget.status_filter,
        widget.vita_transport,
        widget.game_list,
        widget.selection_label,
        widget.destination_label,
        widget.copy_button,
    ):
        _assert_widget_inside(widget, control)

    first = widget.game_list.item(0)
    first.setSelected(True)
    widget.game_list.setCurrentItem(first)
    app.processEvents()

    assert widget.copy_button.isEnabled()
    assert widget.destination_label.text().startswith("Copies to ")
    assert "1 selected" in widget.selection_label.text()
    _assert_widget_inside(widget, widget.copy_button)

    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_vita_status_filter_resets_when_usb_storage_disappears(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    library_root = tmp_path / "library"
    library_root.mkdir()
    vita_root = tmp_path / "vita"
    vita_root.mkdir()

    game = Game(
        path=library_root / "example.vpk",
        name="Example",
        source_platform="psvita",
        size=1024,
        relative=Path("example.vpk"),
    )
    monkeypatch.setattr(local_library_module, "load_config", lambda: {"devices": {}})
    monkeypatch.setattr(local_library_module, "scan_games", lambda _root: [game])

    widget = LocalLibraryWidget(
        {"library_source": {"mode": "local", "local_root": str(library_root)}},
        "vita",
        vita_root,
    )
    widget.show()
    app.processEvents()

    installed_index = widget.status_filter.findText("Installed")
    assert installed_index > 0
    widget.status_filter.blockSignals(True)
    widget.status_filter.setCurrentIndex(installed_index)
    widget.status_filter.blockSignals(False)
    assert widget.status_filter.currentText() == "Installed"

    widget.set_vita(None)
    app.processEvents()

    assert widget.status_filter.currentText() == "All games"
    assert not widget.status_filter.isEnabled()
    assert "VitaShell USB" in widget.status_filter.toolTip()

    widget.close()
    widget.deleteLater()
    app.processEvents()
