from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QSize, Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
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
from .library_sources import LibrarySource, get_library_source, save_library_source
from .romm_api import RomMApiError, normalize_romm_url, test_connection


@dataclass(frozen=True)
class ConsoleProfile:
    key: str
    name: str
    state: str
    accent: str
    subtitle: str


CONSOLES = (
    ConsoleProfile("vita", "PlayStation Vita", "supported", "#3b9cf5", "USB / VitaShell • RetroFlow • Adrenaline"),
    ConsoleProfile("3ds", "Nintendo 3DS", "supported", "#d12228", "FTP / SD card • native 3DS runtimes"),
    ConsoleProfile("ds", "Nintendo DS", "research", "#54b8ff", "Target research • TWiLight Menu++ / flashcards"),
    ConsoleProfile("psp", "PlayStation Portable", "coming", "#8a8f98", "Coming soon"),
    ConsoleProfile("mobile", "Mobile", "coming", "#8a8f98", "Coming soon"),
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
            self.succeeded.emit("PASS • RomM API reachable and platforms.read is available.")
        finally:
            self.finished.emit()


class ConsoleTile(QPushButton):
    TILE_WIDTH = 260
    TILE_HEIGHT = 205

    def __init__(self, profile: ConsoleProfile, parent=None):
        super().__init__(parent)
        self.profile = profile
        selectable = profile.state in {"supported", "research"}
        self.setCheckable(selectable)
        self.setEnabled(selectable)
        self.setFixedSize(QSize(self.TILE_WIDTH, self.TILE_HEIGHT))
        self.setCursor(Qt.CursorShape.PointingHandCursor if self.isEnabled() else Qt.CursorShape.ArrowCursor)
        self.setStyleSheet(self._style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        identity = ConsoleIdentity(profile.key, profile.name, self)
        layout.addWidget(identity, 1)

        sub = QLabel(profile.subtitle)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet("background:transparent;border:none;color:#8f98a6;font-size:10px;padding:0;")
        layout.addWidget(sub)

        labels = {"supported": "SUPPORTED", "research": "RESEARCH", "coming": "COMING SOON"}
        state = QLabel(labels.get(profile.state, profile.state.upper()))
        state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        state.setStyleSheet(
            f"background:transparent;border:none;color:{profile.accent};font-size:9px;font-weight:800;letter-spacing:1px;"
        )
        layout.addWidget(state)

    def _style(self) -> str:
        if self.profile.state == "coming":
            return (
                "QPushButton { background:#12161c; border:1px solid #2b3139; border-radius:16px; }"
                "QPushButton:disabled { color:#707782; }"
            )
        accent = self.profile.accent
        return f"""
            QPushButton {{
                background:#0f1319;
                border:1px solid #2b3139;
                border-radius:16px;
            }}
            QPushButton:hover {{ border-color:{accent}; background:#141a22; }}
            QPushButton:checked {{ border:2px solid {accent}; background:#171d26; }}
        """


class ConsoleGrid(QWidget):
    """Responsive grid that always wraps whole cards and never overlays siblings."""

    def __init__(self, tiles: list[ConsoleTile], parent=None):
        super().__init__(parent)
        self.tiles = tiles
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._columns = 0
        self._relayout()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()

    def _column_count(self) -> int:
        usable = max(0, self.width())
        return max(1, min(3, int((usable + 14) // (ConsoleTile.TILE_WIDTH + 14))))

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
        height = rows * ConsoleTile.TILE_HEIGHT + max(0, rows - 1) * 14
        self.setMinimumHeight(height)


class PlatformSelectorDialog(QDialog):
    """Responsive startup selector for handheld and library context."""

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = dict(config)
        self.source = get_library_source(config)
        self.selected_console = str(config.get("active_console", "vita"))
        self.selected_profile: ConsoleProfile | None = None
        self._romm_thread: QThread | None = None
        self._romm_worker: RomMConnectionWorker | None = None

        self.setWindowTitle("RommHeld")
        self.resize(1120, 820)
        self.setMinimumSize(760, 680)
        self.setStyleSheet("""
            QDialog { background:#080a0e; color:#edf1f6; }
            QGroupBox { border:1px solid #292e36; border-radius:12px; margin-top:10px; padding-top:10px; }
            QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 8px; color:#8f98a6; font-weight:700; }
            QLineEdit { background:#11151b; border:1px solid #333943; border-radius:8px; padding:8px 10px; color:#edf1f6; }
            QLineEdit:disabled { background:#171a20; color:#6f7681; border-color:#292d35; }
            QRadioButton { spacing:8px; color:#d7dce4; }
            QPushButton#browse { background:#171b22; border:1px solid #333943; border-radius:8px; padding:8px 14px; }
            QPushButton#test { background:#171b22; border:1px solid #333943; border-radius:8px; padding:8px 14px; font-weight:700; }
            QPushButton#continue { background:#e8edf4; color:#11151b; border-radius:8px; padding:9px 18px; font-weight:800; }
            QPushButton#exit { background:#171b22; color:#c6ccd5; border:1px solid #333943; border-radius:8px; padding:8px 14px; }
            QLabel#muted { color:#8d96a4; }
            QScrollArea { border:none; background:transparent; }
            QScrollBar:vertical { width:10px; background:#0e1116; margin:0; }
            QScrollBar::handle:vertical { background:#2f657e; border-radius:5px; min-height:28px; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(14)

        title = QLabel("RommHeld")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Sans Serif", 30, QFont.Weight.Bold))
        title.setStyleSheet("color:#f4f6f8; letter-spacing:2px;")
        root.addWidget(title)

        eyebrow = QLabel("SELECT YOUR HANDHELD")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eyebrow.setStyleSheet("color:#7e8794; font-size:10px; letter-spacing:4px;")
        root.addWidget(eyebrow)

        group = QButtonGroup(self)
        group.setExclusive(True)
        tiles: list[ConsoleTile] = []
        for profile in CONSOLES:
            tile = ConsoleTile(profile)
            tiles.append(tile)
            group.addButton(tile)
            tile.clicked.connect(lambda _=False, key=profile.key: self.select_console(key))

        self.console_grid = ConsoleGrid(tiles)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(self.console_grid)
        root.addWidget(scroll, 1)

        source_box = QGroupBox("LIBRARY SOURCE")
        source_layout = QVBoxLayout(source_box)
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
        self.local_browse = QPushButton("Browse…")
        self.local_browse.setObjectName("browse")
        self.local_browse.clicked.connect(self.choose_local_root)
        local_row.addWidget(self.local_edit, 1)
        local_row.addWidget(self.local_browse)
        source_layout.addLayout(local_row)

        server_row = QGridLayout()
        self.url_edit = QLineEdit(self.source.romm_url)
        self.token_edit = QLineEdit(self.source.api_token)
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.test_button = QPushButton("Test server")
        self.test_button.setObjectName("test")
        self.test_button.clicked.connect(self.test_romm_server)
        server_row.addWidget(QLabel("Server URL"), 0, 0)
        server_row.addWidget(self.url_edit, 0, 1)
        server_row.addWidget(QLabel("Client API Token"), 1, 0)
        server_row.addWidget(self.token_edit, 1, 1)
        server_row.addWidget(self.test_button, 1, 2)
        source_layout.addLayout(server_row)

        self.source_status = QLabel()
        self.source_status.setObjectName("muted")
        self.source_status.setWordWrap(True)
        source_layout.addWidget(self.source_status)
        self.local_radio.toggled.connect(self.update_source_visibility)
        self.url_edit.textChanged.connect(self.refresh_source_status)
        self.token_edit.textChanged.connect(self.refresh_source_status)
        root.addWidget(source_box)

        actions = QHBoxLayout()
        exit_button = QPushButton("Exit")
        exit_button.setObjectName("exit")
        exit_button.clicked.connect(self.reject)
        self.continue_button = QPushButton("Continue")
        self.continue_button.setObjectName("continue")
        self.continue_button.clicked.connect(self.continue_selected)
        actions.addWidget(exit_button)
        actions.addStretch()
        actions.addWidget(self.continue_button)
        root.addLayout(actions)

        self.select_console(self.selected_console if self.selected_console in {p.key for p in CONSOLES} else "vita")
        self.update_source_visibility()
        self.refresh_source_status()

    def select_console(self, key: str) -> None:
        profile = next((item for item in CONSOLES if item.key == key), None)
        if profile is None or profile.state not in {"supported", "research"}:
            return
        self.selected_console = key
        self.selected_profile = profile
        for tile in self.console_grid.tiles:
            tile.setChecked(tile.profile.key == key)

    def choose_local_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select local ROM directory", self.local_edit.text())
        if path:
            self.local_edit.setText(path)
            self.local_radio.setChecked(True)
            self.refresh_source_status()

    def update_source_visibility(self) -> None:
        local = self.local_radio.isChecked()
        testing = bool(self._romm_thread and self._romm_thread.isRunning())
        self.local_edit.setEnabled(local and not testing)
        self.local_browse.setEnabled(local and not testing)
        self.url_edit.setEnabled(not local and not testing)
        self.token_edit.setEnabled(not local and not testing)
        self.test_button.setEnabled(not local and not testing)
        self.continue_button.setEnabled(not testing)
        self.refresh_source_status()

    def refresh_source_status(self) -> None:
        if self.local_radio.isChecked():
            root = Path(self.local_edit.text()).expanduser()
            self.source_status.setText(
                "Local source ready." if root.is_dir() else "Choose an existing ROM directory."
            )
        elif self._romm_thread and self._romm_thread.isRunning():
            self.source_status.setText(
                "TESTING… Network activity is isolated to this check. Handheld selection remains available."
            )
        else:
            self.source_status.setText(
                "RomM credentials are stored locally. Platform discovery requires platforms.read."
            )

    def test_romm_server(self) -> None:
        if self._romm_thread and self._romm_thread.isRunning():
            return
        url = self.url_edit.text().strip()
        token = self.token_edit.text().strip()
        if not url or not token:
            self.source_status.setText("Enter the RomM server URL and Client API Token first.")
            return
        try:
            normalize_romm_url(url)
        except ValueError as exc:
            self.source_status.setText(str(exc))
            return

        self.test_button.setText("Testing…")
        self.url_edit.setEnabled(False)
        self.token_edit.setEnabled(False)
        self.test_button.setEnabled(False)
        self.local_edit.setEnabled(False)
        self.local_browse.setEnabled(False)
        self.continue_button.setEnabled(False)

        self._romm_thread = QThread(self)
        self._romm_worker = RomMConnectionWorker(url, token)
        self._romm_worker.moveToThread(self._romm_thread)
        self._romm_thread.started.connect(self._romm_worker.run)
        self._romm_worker.succeeded.connect(self._romm_test_succeeded)
        self._romm_worker.failed.connect(self._romm_test_failed)
        self._romm_worker.finished.connect(self._romm_test_finished)
        self._romm_worker.finished.connect(self._romm_thread.quit)
        self._romm_thread.finished.connect(self._romm_thread.deleteLater)
        self._romm_thread.start()
        self.refresh_source_status()

    @Slot(str)
    def _romm_test_succeeded(self, message: str) -> None:
        self.source_status.setText(message)
        self.test_button.setStyleSheet("background:#1f8f4d;color:white;border-radius:8px;padding:8px 14px;font-weight:700;")

    @Slot(str)
    def _romm_test_failed(self, message: str) -> None:
        self.source_status.setText(f"FAIL • {message}")
        self.test_button.setStyleSheet("background:#b83232;color:white;border-radius:8px;padding:8px 14px;font-weight:700;")

    @Slot()
    def _romm_test_finished(self) -> None:
        if self._romm_thread is not None:
            self._romm_thread.wait(1000)
        self._romm_worker = None
        self._romm_thread = None
        self.test_button.setText("Test again")
        self.test_button.setStyleSheet("")
        self.update_source_visibility()

    def continue_selected(self) -> None:
        if self.selected_profile is None:
            return
        if self.local_radio.isChecked():
            root = Path(self.local_edit.text()).expanduser()
            if not root.is_dir():
                QMessageBox.warning(self, "Library not found", "Choose an existing local ROM directory.")
                return
            source = LibrarySource(mode="local", local_root=str(root))
        else:
            try:
                url = normalize_romm_url(self.url_edit.text())
            except ValueError as exc:
                QMessageBox.warning(self, "RomM configuration", str(exc))
                return
            token = self.token_edit.text().strip()
            if not token:
                QMessageBox.warning(self, "RomM configuration", "Enter the RomM Client API Token.")
                return
            source = LibrarySource(mode="romm_api", romm_url=url, api_token=token)
        updated = save_library_source(self.config, source)
        updated["active_console"] = self.selected_console
        updated["setup_complete"] = True
        save_config(updated)
        self.config = updated
        self.accept()

    def closeEvent(self, event) -> None:
        if self._romm_thread and self._romm_thread.isRunning():
            self._romm_thread.quit()
            self._romm_thread.wait(1000)
        super().closeEvent(event)


def choose_console(config: dict) -> tuple[str | None, dict]:
    dialog = PlatformSelectorDialog(config)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None, config
    return dialog.selected_console, load_config()
