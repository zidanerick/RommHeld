from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QSize, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .config import load_config, save_config
from .console_identity import ConsoleIdentity
from .design_tokens import DARK, brand_for_platform
from .library_sources import (
    LibrarySource,
    get_library_source,
    save_library_source,
    workspace_supports_library_source,
)
from .romm_api import RomMApiError, normalize_romm_url, test_connection
from .ui_components import AccentButton


@dataclass(frozen=True)
class ConsoleProfile:
    key: str
    name: str
    state: str
    accent: str
    subtitle: str


CONSOLES = (
    ConsoleProfile(
        "vita",
        "PlayStation Vita",
        "supported",
        brand_for_platform("vita").accent,
        "VitaShell • RetroFlow • Adrenaline",
    ),
    ConsoleProfile(
        "3ds",
        "Nintendo 3DS",
        "supported",
        brand_for_platform("3ds").accent,
        "FTP • FBI Remote Install • native runtimes",
    ),
    ConsoleProfile(
        "ds",
        "Nintendo DS",
        "research",
        brand_for_platform("ds").accent,
        "TWiLight Menu++ • nds-bootstrap • flashcards",
    ),
    ConsoleProfile(
        "psp",
        "PlayStation Portable",
        "coming",
        brand_for_platform("psp").accent,
        "Coming soon",
    ),
    ConsoleProfile(
        "mobile",
        "Mobile",
        "coming",
        brand_for_platform("mobile").accent,
        "Coming soon",
    ),
)


class RomMConnectionWorker(QObject):
    succeeded = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, url: str, token: str):
        super().__init__()
        self.url = url
        self.token = token

    @Slot()
    def run(self) -> None:
        try:
            test_connection(normalize_romm_url(self.url), self.token)
        except (RomMApiError, ValueError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Unexpected connection error: {exc}")
        else:
            self.succeeded.emit("RomM connected • API access verified")
        finally:
            self.finished.emit()


class ConsoleTile(QFrame):
    """Clickable handheld card that stays stable across Linux Qt styles."""

    clicked = Signal()
    TILE_WIDTH = 250
    TILE_HEIGHT = 170

    def __init__(self, profile: ConsoleProfile, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.selectable = profile.state in {"supported", "research"}
        self._selected = False

        self.setObjectName("consoleTile")
        self.setFixedSize(QSize(self.TILE_WIDTH, self.TILE_HEIGHT))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus if self.selectable else Qt.FocusPolicy.NoFocus
        )
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if self.selectable
            else Qt.CursorShape.ArrowCursor
        )
        self.setProperty("selected", False)
        self.setStyleSheet(self._style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 8)
        layout.setSpacing(3)

        identity = ConsoleIdentity(profile.key, profile.name, self)
        identity.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(identity, 1)

        sub = QLabel(profile.subtitle)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        sub.setStyleSheet(
            f"background:transparent;border:none;color:{DARK.text_secondary};font-size:9px;padding:0;"
        )
        layout.addWidget(sub)

        labels = {
            "supported": "Ready",
            "research": "In development",
            "coming": "Coming soon",
        }
        state = QLabel(labels.get(profile.state, profile.state.title()))
        state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        state.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        state.setStyleSheet(
            f"background:transparent;border:none;color:{profile.accent};font-size:9px;font-weight:700;padding:0;"
        )
        layout.addWidget(state)

    def _style(self) -> str:
        if not self.selectable:
            return f"""
                QFrame#consoleTile {{
                    background:#171719;
                    border:1px solid #29292C;
                    border-radius:15px;
                }}
            """

        accent = self.profile.accent
        soft = brand_for_platform(self.profile.key).accent_soft
        return f"""
            QFrame#consoleTile {{
                background:{DARK.surface};
                border:1px solid {DARK.separator};
                border-radius:15px;
            }}
            QFrame#consoleTile:hover {{
                border:1px solid {accent};
                background:{DARK.surface_raised};
            }}
            QFrame#consoleTile[selected="true"] {{
                border:2px solid {accent};
                background:{soft};
            }}
            QFrame#consoleTile:focus {{
                border:2px solid {DARK.text_primary};
            }}
        """

    def set_selected(self, selected: bool) -> None:
        selected = bool(selected and self.selectable)
        if self._selected == selected:
            return
        self._selected = selected
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event) -> None:
        if self.selectable and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if self.selectable and event.key() in {
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        }:
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class ConsoleGrid(QWidget):
    """Responsive grid that always wraps complete handheld cards."""

    def __init__(self, tiles: list[ConsoleTile], parent=None):
        super().__init__(parent)
        self.tiles = tiles
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._columns = 0
        self._relayout()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()

    def _column_count(self) -> int:
        usable = max(0, self.width())
        return max(
            1,
            min(3, int((usable + 12) // (ConsoleTile.TILE_WIDTH + 12))),
        )

    def _relayout(self) -> None:
        columns = self._column_count()
        if columns == self._columns:
            return
        self._columns = columns

        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(self)

        for index, tile in enumerate(self.tiles):
            self.grid.addWidget(tile, index // columns, index % columns)

        rows = (len(self.tiles) + columns - 1) // columns
        height = rows * ConsoleTile.TILE_HEIGHT + max(0, rows - 1) * 12
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)


class PlatformSelectorDialog(QDialog):
    """Startup selector for the active handheld and library source."""

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = dict(config)
        self.source = get_library_source(config)
        self.selected_console = str(config.get("active_console", "vita"))
        self.selected_profile: ConsoleProfile | None = None
        self._romm_thread: QThread | None = None
        self._romm_worker: RomMConnectionWorker | None = None

        self.setWindowTitle("RommHeld")
        self.resize(1080, 780)
        self.setMinimumSize(760, 650)
        self.setStyleSheet(self._stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 20, 26, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.setContentsMargins(0, 0, 0, 0)
        title_group.setSpacing(2)
        title = QLabel("RommHeld")
        title.setObjectName("selectorTitle")
        subtitle = QLabel("Choose a handheld and library source")
        subtitle.setObjectName("selectorSubtitle")
        title_group.addWidget(title)
        title_group.addWidget(subtitle)
        header.addLayout(title_group, 1)
        self.selection_context = QLabel()
        self.selection_context.setObjectName("selectionContext")
        header.addWidget(self.selection_context, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        handheld_heading = QLabel("HANDHELD")
        handheld_heading.setObjectName("selectorHeading")
        root.addWidget(handheld_heading)

        tiles: list[ConsoleTile] = []
        for profile in CONSOLES:
            tile = ConsoleTile(profile)
            tiles.append(tile)
            tile.clicked.connect(lambda key=profile.key: self.select_console(key))

        self.console_grid = ConsoleGrid(tiles)
        scroll = QScrollArea()
        scroll.setObjectName("consoleScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setMinimumHeight(ConsoleTile.TILE_HEIGHT * 2 + 12)
        scroll.setWidget(self.console_grid)
        root.addWidget(scroll, 1)

        source_box = QGroupBox("Library source")
        source_layout = QVBoxLayout(source_box)
        source_layout.setSpacing(9)
        source_row = QHBoxLayout()
        self.local_radio = QRadioButton("Local ROM directory")
        self.romm_radio = QRadioButton("RomM server")
        self.local_radio.setChecked(self.source.mode == "local")
        self.romm_radio.setChecked(self.source.mode == "romm_api")
        source_row.addWidget(self.local_radio)
        source_row.addWidget(self.romm_radio)
        source_row.addStretch()
        source_layout.addLayout(source_row)

        local_row = QHBoxLayout()
        self.local_edit = QLineEdit(self.source.local_root)
        self.local_edit.setPlaceholderText("Choose a local ROM directory")
        self.local_browse = QPushButton("Browse…")
        self.local_browse.clicked.connect(self.choose_local_root)
        local_row.addWidget(self.local_edit, 1)
        local_row.addWidget(self.local_browse)
        source_layout.addLayout(local_row)

        server_row = QGridLayout()
        server_row.setHorizontalSpacing(8)
        server_row.setVerticalSpacing(7)
        self.url_edit = QLineEdit(self.source.romm_url)
        self.url_edit.setPlaceholderText("https://romm.example.com")
        self.token_edit = QLineEdit(self.source.api_token)
        self.token_edit.setPlaceholderText("Client API Token")
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.test_button = QPushButton("Test connection")
        self.test_button.clicked.connect(self.test_romm_server)
        server_row.addWidget(QLabel("Server"), 0, 0)
        server_row.addWidget(self.url_edit, 0, 1, 1, 2)
        server_row.addWidget(QLabel("Token"), 1, 0)
        server_row.addWidget(self.token_edit, 1, 1)
        server_row.addWidget(self.test_button, 1, 2)
        source_layout.addLayout(server_row)

        self.source_status = QLabel()
        self.source_status.setObjectName("sourceStatus")
        self.source_status.setWordWrap(True)
        self.source_status.setProperty("state", "neutral")
        source_layout.addWidget(self.source_status)
        self.local_radio.toggled.connect(self.update_source_visibility)
        self.url_edit.textChanged.connect(self.refresh_source_status)
        self.token_edit.textChanged.connect(self.refresh_source_status)
        root.addWidget(source_box)

        actions = QHBoxLayout()
        exit_button = QPushButton("Exit")
        exit_button.setProperty("quiet", True)
        exit_button.clicked.connect(self.reject)
        initial_accent = brand_for_platform(self.selected_console).accent
        self.continue_button = AccentButton("Continue", initial_accent)
        self.continue_button.clicked.connect(self.continue_selected)
        actions.addWidget(exit_button)
        actions.addStretch()
        actions.addWidget(self.continue_button)
        root.addLayout(actions)

        valid_keys = {p.key for p in CONSOLES}
        self.select_console(
            self.selected_console if self.selected_console in valid_keys else "vita"
        )
        self.update_source_visibility()
        self.refresh_source_status()

    def _stylesheet(self) -> str:
        return f"""
        QDialog {{ background:{DARK.background}; color:{DARK.text_primary}; }}
        QLabel#selectorTitle {{ color:{DARK.text_primary}; font-size:28px; font-weight:700; }}
        QLabel#selectorSubtitle {{ color:{DARK.text_secondary}; font-size:11px; }}
        QLabel#selectorHeading {{
            color:{DARK.text_tertiary};
            font-size:9px;
            font-weight:700;
            letter-spacing:1px;
            padding-top:3px;
        }}
        QLabel#selectionContext {{
            background:{DARK.surface};
            color:{DARK.text_secondary};
            border:1px solid {DARK.separator};
            border-radius:9px;
            padding:6px 10px;
            font-size:10px;
        }}
        QScrollArea#consoleScroll {{ border:none; background:transparent; }}
        QScrollArea#consoleScroll > QWidget > QWidget {{ background:transparent; }}
        QGroupBox {{
            background:{DARK.surface};
            border:1px solid {DARK.separator};
            border-radius:13px;
            margin-top:14px;
            padding-top:12px;
        }}
        QGroupBox::title {{
            subcontrol-origin:margin;
            left:12px;
            padding:0 6px;
            color:{DARK.text_secondary};
            font-weight:600;
        }}
        QRadioButton {{
            spacing:7px;
            padding:4px 6px;
            color:{DARK.text_primary};
            background:transparent;
        }}
        QLabel#sourceStatus {{ color:{DARK.text_secondary}; font-size:10px; }}
        QLabel#sourceStatus[state="success"] {{ color:{DARK.success}; }}
        QLabel#sourceStatus[state="error"] {{ color:{DARK.error}; }}
        QLabel#sourceStatus[state="busy"] {{ color:{DARK.warning}; }}
        """

    def _set_source_state(self, state: str, text: str) -> None:
        self.source_status.setProperty("state", state)
        self.source_status.setText(text)
        self.source_status.style().unpolish(self.source_status)
        self.source_status.style().polish(self.source_status)
        self.source_status.update()

    def _romm_supported(self) -> bool:
        return workspace_supports_library_source(self.selected_console, "romm_api")

    def select_console(self, key: str) -> None:
        profile = next((item for item in CONSOLES if item.key == key), None)
        if profile is None or profile.state not in {"supported", "research"}:
            return
        self.selected_console = key
        self.selected_profile = profile
        for tile in self.console_grid.tiles:
            tile.set_selected(tile.profile.key == key)
        self.continue_button.set_accent(profile.accent)
        self.selection_context.setText(profile.name)
        self.update_source_visibility()

    def choose_local_root(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select local ROM directory",
            self.local_edit.text(),
        )
        if path:
            self.local_edit.setText(path)
            self.local_radio.setChecked(True)
            self.refresh_source_status()

    def update_source_visibility(self) -> None:
        romm_supported = self._romm_supported()
        if not romm_supported and self.romm_radio.isChecked():
            self.local_radio.setChecked(True)

        local = self.local_radio.isChecked()
        testing = bool(self._romm_thread and self._romm_thread.isRunning())
        self.local_edit.setEnabled(local and not testing)
        self.local_browse.setEnabled(local and not testing)
        self.romm_radio.setEnabled(romm_supported and not testing)
        self.romm_radio.setToolTip(
            ""
            if romm_supported
            else "RomM library browsing is currently available in the Nintendo 3DS workspace."
        )
        self.url_edit.setEnabled(romm_supported and not local and not testing)
        self.token_edit.setEnabled(romm_supported and not local and not testing)
        self.test_button.setEnabled(romm_supported and not local and not testing)
        self.continue_button.setEnabled(not testing)
        self.refresh_source_status()

    def refresh_source_status(self) -> None:
        if self.local_radio.isChecked():
            root = Path(self.local_edit.text()).expanduser()
            target = self.selected_profile.name if self.selected_profile is not None else "this handheld"
            if root.is_dir():
                self._set_source_state("success", f"Local library ready for {target}")
            elif not self._romm_supported():
                self._set_source_state(
                    "neutral",
                    f"{target} currently uses a local library. Choose an existing ROM directory.",
                )
            else:
                self._set_source_state("neutral", "Choose an existing ROM directory")
        elif self._romm_thread and self._romm_thread.isRunning():
            self._set_source_state("busy", "Testing RomM connection…")
        else:
            self._set_source_state(
                "neutral",
                "RomM uses the saved server URL and Client API Token",
            )

    def test_romm_server(self) -> None:
        if not self._romm_supported():
            self.refresh_source_status()
            return
        if self._romm_thread and self._romm_thread.isRunning():
            return
        url = self.url_edit.text().strip()
        token = self.token_edit.text().strip()
        if not url or not token:
            self._set_source_state(
                "error",
                "Enter the RomM server URL and Client API Token first",
            )
            return
        try:
            normalize_romm_url(url)
        except ValueError as exc:
            self._set_source_state("error", str(exc))
            return

        self.test_button.setText("Testing…")
        self.url_edit.setEnabled(False)
        self.token_edit.setEnabled(False)
        self.test_button.setEnabled(False)
        self.local_edit.setEnabled(False)
        self.local_browse.setEnabled(False)
        self.continue_button.setEnabled(False)

        thread = QThread(self)
        worker = RomMConnectionWorker(url, token)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._romm_test_succeeded)
        worker.failed.connect(self._romm_test_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._romm_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._romm_thread = thread
        self._romm_worker = worker
        thread.start()
        self.refresh_source_status()

    @Slot(str)
    def _romm_test_succeeded(self, message: str) -> None:
        self._set_source_state("success", message)

    @Slot(str)
    def _romm_test_failed(self, message: str) -> None:
        self._set_source_state("error", f"RomM unavailable • {message}")

    @Slot()
    def _romm_thread_finished(self) -> None:
        self._romm_worker = None
        self._romm_thread = None
        self.test_button.setText("Test connection")
        self.update_source_visibility()

    def continue_selected(self) -> None:
        if self.selected_profile is None:
            return
        mode = "local" if self.local_radio.isChecked() else "romm_api"
        if not workspace_supports_library_source(self.selected_console, mode):
            QMessageBox.warning(
                self,
                "Library source unavailable",
                f"{self.selected_profile.name} does not currently have a {('RomM' if mode == 'romm_api' else 'local')} library browser. Choose an available library source.",
            )
            return

        saved_romm_url = self.url_edit.text().strip()
        saved_token = self.token_edit.text().strip()
        saved_local_root = self.local_edit.text().strip()
        if self.local_radio.isChecked():
            root = Path(saved_local_root).expanduser()
            if not root.is_dir():
                QMessageBox.warning(
                    self,
                    "Library not found",
                    "Choose an existing local ROM directory.",
                )
                return
            source = LibrarySource(
                mode="local",
                local_root=str(root),
                romm_url=saved_romm_url,
                api_token=saved_token,
            )
        else:
            try:
                url = normalize_romm_url(saved_romm_url)
            except ValueError as exc:
                QMessageBox.warning(self, "RomM configuration", str(exc))
                return
            if not saved_token:
                QMessageBox.warning(
                    self,
                    "RomM configuration",
                    "Enter the RomM Client API Token.",
                )
                return
            source = LibrarySource(
                mode="romm_api",
                local_root=saved_local_root,
                romm_url=url,
                api_token=saved_token,
            )
        updated = save_library_source(self.config, source)
        updated["active_console"] = self.selected_console
        updated["setup_complete"] = True
        save_config(updated)
        self.config = updated
        self.accept()

    def reject(self) -> None:
        thread = self._romm_thread
        if thread is not None and thread.isRunning():
            self._set_source_state(
                "busy",
                "Finish the RomM connection test before closing setup.",
            )
            return
        super().reject()

    def closeEvent(self, event) -> None:
        thread = self._romm_thread
        if thread is not None and thread.isRunning():
            self._set_source_state(
                "busy",
                "Finish the RomM connection test before closing setup.",
            )
            event.ignore()
            return
        for tile in self.console_grid.tiles:
            identity = tile.findChild(ConsoleIdentity)
            if identity is not None:
                identity.stop_loading()
        super().closeEvent(event)


def choose_console(config: dict) -> tuple[str | None, dict]:
    dialog = PlatformSelectorDialog(config)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None, config
    return dialog.selected_console, load_config()
