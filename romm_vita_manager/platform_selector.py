from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, QObject, QSize, Qt, Signal, Slot
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
    QSizePolicy,
    QVBoxLayout,
)

from .config import load_config, save_config
from .library_sources import LibrarySource, get_library_source, save_library_source
from .romm_api import RomMApiError, normalize_romm_url, test_connection


@dataclass(frozen=True)
class ConsoleProfile:
    key: str
    name: str
    family: str
    state: str
    accent: str
    secondary: str
    subtitle: str


CONSOLES = (
    ConsoleProfile("vita", "PlayStation Vita", "Sony handheld", "supported", "#41a6f6", "#17324d", "USB / VitaShell • RetroFlow • Adrenaline"),
    ConsoleProfile("3ds", "Nintendo 3DS", "Nintendo handheld", "supported", "#e53935", "#4a1212", "FTP / SD card • native 3DS runtimes"),
    ConsoleProfile("ds", "Nintendo DS", "Nintendo handheld", "supported", "#54b8ff", "#122a45", "TWiLight Menu++ • nds-bootstrap • flashcards"),
    ConsoleProfile("psp", "PlayStation Portable", "Sony handheld", "coming", "#777777", "#202020", "Coming soon"),
    ConsoleProfile("mobile", "Mobile", "General", "coming", "#777777", "#202020", "Coming soon"),
)


class RomMConnectionWorker(QObject):
    succeeded = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, url: str, token: str, parent: QObject | None = None):
        super().__init__(parent)
        self.url = url
        self.token = token

    @Slot()
    def run(self) -> None:
        try:
            instance_url = normalize_romm_url(self.url)
            test_connection(instance_url, self.token)
        except (RomMApiError, ValueError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Unexpected connection error: {exc}")
        else:
            self.succeeded.emit("RomM API connection successful. platforms.read is available.")
        finally:
            self.finished.emit()


class ConsoleTile(QPushButton):
    def __init__(self, profile: ConsoleProfile, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.setCheckable(profile.state == "supported")
        self.setEnabled(profile.state == "supported")
        self.setMinimumSize(QSize(250, 170))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setProperty("accent", profile.accent)
        self.setProperty("coming", profile.state == "coming")
        self.setCursor(Qt.CursorShape.PointingHandCursor if self.isEnabled() else Qt.CursorShape.ArrowCursor)
        self.setText("")
        self.setStyleSheet(self._style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        glyph = QLabel(self._glyph(profile.key))
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setFont(QFont("Sans Serif", 38, QFont.Weight.Bold))
        glyph.setStyleSheet(f"color: {profile.accent}; background: transparent; border: none;")
        layout.addWidget(glyph)

        title = QLabel(profile.name)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Sans Serif", 16, QFont.Weight.Bold))
        title.setStyleSheet("background: transparent; border: none; color: #f2f4f8;")
        layout.addWidget(title)

        sub = QLabel(profile.subtitle)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet("background: transparent; border: none; color: #aeb6c2; font-size: 11px;")
        layout.addWidget(sub)

    @staticmethod
    def _glyph(key: str) -> str:
        return {"vita": "▣", "3ds": "▦", "ds": "▤", "psp": "▰", "mobile": "◉"}.get(key, "■")

    def _style(self) -> str:
        accent = self.profile.accent
        secondary = self.profile.secondary
        if self.profile.state == "coming":
            return """
                QPushButton { background: #17191e; border: 1px solid #343840; border-radius: 14px; color: #808691; }
                QPushButton:disabled { color: #666b74; }
            """
        return f"""
            QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {secondary}, stop:1 #101216); border: 2px solid #2d323c; border-radius: 14px; }}
            QPushButton:hover {{ border: 2px solid {accent}; }}
            QPushButton:checked {{ border: 3px solid {accent}; background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {secondary}, stop:1 #151920); }}
        """


class PlatformSelectorDialog(QDialog):
    """Original console-selection launch screen for RommHeld."""

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = dict(config)
        self.selected_console = str(config.get("active_console", "vita"))
        self.source = get_library_source(config)
        self.selected_profile: ConsoleProfile | None = None
        self._romm_thread: QThread | None = None
        self._romm_worker: RomMConnectionWorker | None = None
        self.setWindowTitle("RommHeld")
        self.resize(1120, 820)
        self.setMinimumSize(980, 720)

        self.setStyleSheet("""
            QDialog { background: #090b0f; color: #eef1f5; }
            QGroupBox { border: 1px solid #292d34; border-radius: 12px; margin-top: 10px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 8px; color: #9aa3af; font-weight: 700; }
            QLineEdit { background: #101318; border: 1px solid #343943; border-radius: 8px; padding: 8px 10px; color: #eef1f5; }
            QRadioButton { spacing: 8px; color: #d6dbe2; }
            QPushButton.action { background: #e8edf4; color: #111318; border-radius: 8px; padding: 9px 16px; font-weight: 700; }
            QPushButton.secondary { background: #171a20; color: #c8ced7; border: 1px solid #343943; border-radius: 8px; padding: 8px 14px; }
            QLabel.muted { color: #8e96a3; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        title = QLabel("RommHeld")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Sans Serif", 30, QFont.Weight.Bold))
        title.setStyleSheet("letter-spacing: 2px; color: #f6f7f9;")
        root.addWidget(title)

        subtitle = QLabel("SELECT YOUR HANDHELD")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("letter-spacing: 4px; color: #8c95a2; font-size: 11px;")
        root.addWidget(subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        group = QButtonGroup(self)
        group.setExclusive(True)
        self.tiles: dict[str, ConsoleTile] = {}
        for i, profile in enumerate(CONSOLES):
            tile = ConsoleTile(profile)
            self.tiles[profile.key] = tile
            group.addButton(tile)
            tile.clicked.connect(lambda _checked=False, key=profile.key: self.select_console(key))
            grid.addWidget(tile, i // 3, i % 3)
        root.addLayout(grid, 1)

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
        local_browse = QPushButton("Browse…")
        local_browse.setProperty("class", "secondary")
        local_browse.clicked.connect(self.choose_local_root)
        local_row.addWidget(self.local_edit, 1)
        local_row.addWidget(local_browse)
        source_layout.addLayout(local_row)

        server_form = QGridLayout()
        self.url_edit = QLineEdit(self.source.romm_url)
        self.token_edit = QLineEdit(self.source.api_token)
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.test_button = QPushButton("Test server")
        self.test_button.clicked.connect(self.test_romm_server)
        server_form.addWidget(QLabel("Server URL"), 0, 0)
        server_form.addWidget(self.url_edit, 0, 1)
        server_form.addWidget(QLabel("Client API Token"), 1, 0)
        server_form.addWidget(self.token_edit, 1, 1)
        server_form.addWidget(self.test_button, 1, 2)
        source_layout.addLayout(server_form)

        self.source_status = QLabel()
        self.source_status.setProperty("class", "muted")
        self.source_status.setWordWrap(True)
        source_layout.addWidget(self.source_status)
        self.local_radio.toggled.connect(self.update_source_visibility)
        self.url_edit.textChanged.connect(self.refresh_source_status)
        self.token_edit.textChanged.connect(self.refresh_source_status)
        self.update_source_visibility()
        self.refresh_source_status()
        root.addWidget(source_box)

        actions = QHBoxLayout()
        self.back_button = QPushButton("Exit")
        self.back_button.clicked.connect(self.reject)
        self.continue_button = QPushButton("Continue")
        self.continue_button.setProperty("class", "action")
        self.continue_button.clicked.connect(self.continue_selected)
        actions.addWidget(self.back_button)
        actions.addStretch()
        actions.addWidget(self.continue_button)
        root.addLayout(actions)

        self.select_console(self.selected_console if self.selected_console in self.tiles else "vita")

    def select_console(self, key: str) -> None:
        profile = next((p for p in CONSOLES if p.key == key), None)
        if profile is None or profile.state != "supported":
            return
        self.selected_console = key
        self.selected_profile = profile
        for tile_key, tile in self.tiles.items():
            tile.setChecked(tile_key == key)

    def choose_local_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select local ROM directory", self.local_edit.text())
        if path:
            self.local_edit.setText(path)
            self.local_radio.setChecked(True)
            self.refresh_source_status()

    def update_source_visibility(self) -> None:
        local = self.local_radio.isChecked()
        self.local_edit.setEnabled(local)
        for widget in (self.url_edit, self.token_edit, self.test_button):
            widget.setEnabled(not local)
        self.refresh_source_status()

    def refresh_source_status(self) -> None:
        if self.local_radio.isChecked():
            root = Path(self.local_edit.text()).expanduser()
            self.source_status.setText("Local source ready." if root.is_dir() else "Choose an existing ROM directory.")
        elif self._romm_thread and self._romm_thread.isRunning():
            self.source_status.setText("Testing RomM API connection… You can continue editing the URL or token while this runs.")
        else:
            self.source_status.setText("RomM server credentials are stored locally and used by the API provider.")

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
        self.test_button.setEnabled(False)
        self.test_button.setToolTip("RomM connection test in progress")
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
        self.test_button.setText("PASS")
        self.test_button.setStyleSheet("background: #1f8f4d; color: white; border-radius: 8px; padding: 9px 16px; font-weight: 700;")
        self.test_button.setEnabled(True)
        self.test_button.setToolTip("Click to test the RomM server again")

    @Slot(str)
    def _romm_test_failed(self, message: str) -> None:
        self.source_status.setText(message)
        self.test_button.setText("FAIL")
        self.test_button.setStyleSheet("background: #b83232; color: white; border-radius: 8px; padding: 9px 16px; font-weight: 700;")
        self.test_button.setEnabled(True)
        self.test_button.setToolTip("Click to test the RomM server again")

    @Slot()
    def _romm_test_finished(self) -> None:
        if self._romm_thread is not None:
            self._romm_thread.wait(1000)
        self._romm_worker = None
        self._romm_thread = None

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
