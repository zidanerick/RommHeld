from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from .config import save_config
from .library_sources import get_library_source
from .romm import scan_games
from .romm_remote import RomMRemoteGame, download_rom, list_3ds_games
from .three_ds_ftp import ThreeDSFtpBackend, ThreeDSFtpSettings
from .three_ds_paths import default_3ds_destination


class ThreeDSConnectionWorker(QThread):
    succeeded = Signal()
    failed = Signal(str)

    def __init__(self, settings: ThreeDSFtpSettings):
        super().__init__()
        self.settings = settings

    def run(self) -> None:
        backend = ThreeDSFtpBackend(self.settings)
        try:
            backend.connect()
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit()
        finally:
            backend.close()


class ThreeDSTransferWorker(QThread):
    progress = Signal(int)
    status_changed = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        settings: ThreeDSFtpSettings,
        source: Path | None,
        destination: str,
        *,
        remote_game: RomMRemoteGame | None = None,
        romm_url: str = "",
        romm_token: str = "",
    ):
        super().__init__()
        self.settings = settings
        self.source = source
        self.destination = destination
        self.remote_game = remote_game
        self.romm_url = romm_url
        self.romm_token = romm_token
        self.cancel_event = threading.Event()
        self.backend: ThreeDSFtpBackend | None = None
        self._temporary_path: Path | None = None

    def cancel(self) -> None:
        self.cancel_event.set()

    def _resolve_source(self) -> Path:
        if self.source is not None:
            if not self.source.is_file():
                raise FileNotFoundError(f"Source file does not exist: {self.source}")
            return self.source
        if self.remote_game is None:
            raise ValueError("No transfer source was selected.")
        if not self.romm_url.strip() or not self.romm_token.strip():
            raise ValueError("RomM server credentials are not configured.")

        handle = tempfile.NamedTemporaryFile(prefix="rommheld-3ds-", suffix=Path(self.remote_game.filename).suffix, delete=False)
        handle.close()
        self._temporary_path = Path(handle.name)
        self.status_changed.emit(f"Downloading {self.remote_game.name} from RomM…")
        return download_rom(self.romm_url, self.romm_token, self.remote_game, self._temporary_path)

    def run(self) -> None:
        try:
            source = self._resolve_source()
            self.status_changed.emit(f"Transferring {self.remote_game.name if self.remote_game else source.name} to the 3DS…")
            self.backend = ThreeDSFtpBackend(self.settings)
            self.backend.connect()
            result, _ = self.backend.upload(
                source,
                self.destination,
                cancel_event=self.cancel_event,
                progress=self.progress.emit,
            )
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if self.backend is not None:
                self.backend.close()
            if self._temporary_path is not None:
                try:
                    self._temporary_path.unlink(missing_ok=True)
                except Exception:
                    pass


class ThreeDSManagerDialog(QDialog):
    """3DS deployment surface for local or RomM-backed library content."""

    def __init__(self, config: dict, library_root: Path | None = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.library_source = get_library_source(config)
        self.library_root = library_root.expanduser() if library_root else None
        self.connection_worker: ThreeDSConnectionWorker | None = None
        self.worker: ThreeDSTransferWorker | None = None
        self._connected = False

        self.setWindowTitle("Nintendo 3DS Manager")
        self.resize(960, 700)

        saved = config.get("devices", {}).get("3ds", {})
        self.host_edit = QLineEdit(str(saved.get("host", "")))
        self.port_edit = QLineEdit(str(saved.get("port", 5000)))
        self.user_edit = QLineEdit(str(saved.get("username", "anonymous")))
        self.password_edit = QLineEdit(str(saved.get("password", "")))
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.root_edit = QLineEdit(str(saved.get("remote_root", "/")))

        self.connect_button = QPushButton("Connect")
        self.refresh_button = QPushButton("Refresh Library")
        self.connect_button.clicked.connect(self.connect_3ds)
        self.refresh_button.clicked.connect(self.refresh_library)

        form = QFormLayout()
        form.addRow("Host:", self.host_edit)
        form.addRow("Port:", self.port_edit)
        form.addRow("Username:", self.user_edit)
        form.addRow("Password:", self.password_edit)
        form.addRow("Remote root:", self.root_edit)

        connection_row = QHBoxLayout()
        connection_row.addWidget(self.connect_button)
        connection_row.addWidget(self.refresh_button)
        connection_row.addStretch()

        self.status = QLabel("Connect to the 3DS FTP server to deploy a library game.")
        self.status.setWordWrap(True)

        self.game_list = QListWidget()
        self.game_list.itemSelectionChanged.connect(self.game_selected)

        self.source_label = QLabel()
        self.source_label.setWordWrap(True)

        self.destination_edit = QLineEdit()
        self.destination_edit.setPlaceholderText("Remote destination, for example /roms/nds/Game.nds")
        self.send_button = QPushButton("Send Selected Game")
        self.cancel_button = QPushButton("Cancel Transfer")
        self.cancel_button.setEnabled(False)
        self.send_button.clicked.connect(self.send_selected)
        self.cancel_button.clicked.connect(self.cancel_transfer)

        transfer_row = QHBoxLayout()
        transfer_row.addWidget(self.destination_edit, 1)
        transfer_row.addWidget(self.send_button)
        transfer_row.addWidget(self.cancel_button)

        self.progress = QProgressBar()

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(connection_row)
        layout.addWidget(self.status)
        layout.addWidget(QLabel("Library games:"))
        layout.addWidget(self.game_list, 1)
        layout.addWidget(self.source_label)
        layout.addWidget(QLabel("Remote destination:"))
        layout.addLayout(transfer_row)
        layout.addWidget(self.progress)

        close = QPushButton("Close")
        close.clicked.connect(self.close)
        layout.addWidget(close)

        self.refresh_library()
        self._update_controls()

    def settings(self) -> ThreeDSFtpSettings:
        try:
            port = int(self.port_edit.text().strip())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError as exc:
            raise ValueError("FTP port must be between 1 and 65535.") from exc
        return ThreeDSFtpSettings(
            host=self.host_edit.text().strip(),
            port=port,
            username=self.user_edit.text().strip() or "anonymous",
            password=self.password_edit.text(),
            remote_root=self.root_edit.text().strip() or "/",
        )

    def save_settings(self) -> None:
        cfg = dict(self.config)
        devices = dict(cfg.get("devices", {}))
        devices["3ds"] = {
            "host": self.host_edit.text().strip(),
            "port": int(self.port_edit.text()),
            "username": self.user_edit.text().strip() or "anonymous",
            "password": self.password_edit.text(),
            "remote_root": self.root_edit.text().strip() or "/",
        }
        cfg["devices"] = devices
        save_config(cfg)
        self.config = cfg

    def connect_3ds(self) -> None:
        if self.connection_worker and self.connection_worker.isRunning():
            return
        if self.worker and self.worker.isRunning():
            return
        try:
            settings = self.settings()
            self.save_settings()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid FTP settings", str(exc))
            return

        self.status.setText("Connecting to 3DS FTP…")
        self.connection_worker = ThreeDSConnectionWorker(settings)
        self.connection_worker.succeeded.connect(self.connection_succeeded)
        self.connection_worker.failed.connect(self.connection_failed)
        self.connection_worker.finished.connect(self._connection_finished)
        self._update_controls()
        self.connection_worker.start()

    def connection_succeeded(self) -> None:
        self._connected = True
        self.status.setText("Connected to the 3DS FTP server. Transfers verify destination sizes and protect different-size files.")
        self._update_controls()

    def connection_failed(self, message: str) -> None:
        self._connected = False
        self.status.setText(f"Connection failed: {message}")
        self._update_controls()

    def _connection_finished(self) -> None:
        self.connection_worker = None
        self._update_controls()

    def refresh_library(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        self.game_list.clear()
        if self.library_source.mode == "romm_api":
            self.source_label.setText("RomM Server • loading Nintendo 3DS library…")
            try:
                games = list_3ds_games(self.library_source.romm_url, self.library_source.api_token)
            except Exception as exc:
                self.source_label.setText(f"RomM Server • unable to load library: {exc}")
                self._update_controls()
                return
            self.source_label.setText(f"RomM Server • {len(games)} Nintendo 3DS library files")
            for game in games:
                item = QListWidgetItem(f"{game.name} • {game.platform} • {game.size:,} bytes")
                item.setData(256, game)
                self.game_list.addItem(item)
            if games:
                self.game_list.setCurrentRow(0)
            self._update_controls()
            return

        root = self.library_root
        if root is None or not root.is_dir():
            self.source_label.setText("No local library directory is configured. Select a local library in Library Settings first.")
            self._update_controls()
            return
        games = scan_games(root)
        self.source_label.setText(f"{root} • {len(games)} library files")
        for game in games:
            item = QListWidgetItem(f"{game.name} • {game.source_platform} • {game.size:,} bytes")
            item.setData(256, game)
            self.game_list.addItem(item)
        if games:
            self.game_list.setCurrentRow(0)

    def game_selected(self) -> None:
        item = self.game_list.currentItem()
        if item is None:
            self.destination_edit.clear()
            self._update_controls()
            return
        game = item.data(256)
        filename = game.filename if isinstance(game, RomMRemoteGame) else game.path.name
        suffix = Path(filename).suffix
        self.destination_edit.setText(default_3ds_destination(filename, suffix))
        self._update_controls()

    def _selected_game(self):
        item = self.game_list.currentItem()
        return item.data(256) if item is not None else None

    def _update_controls(self) -> None:
        running = bool(
            (self.connection_worker and self.connection_worker.isRunning())
            or (self.worker and self.worker.isRunning())
        )
        selected = self._selected_game() is not None
        self.connect_button.setEnabled(not running)
        self.refresh_button.setEnabled(not running)
        self.send_button.setEnabled(self._connected and selected and not running)
        self.cancel_button.setEnabled(bool(self.worker and self.worker.isRunning()))
        for widget in (self.host_edit, self.port_edit, self.user_edit, self.password_edit, self.root_edit, self.destination_edit):
            widget.setEnabled(not running)

    def send_selected(self) -> None:
        selected = self._selected_game()
        if selected is None:
            return

        source: Path | None = None
        remote_game: RomMRemoteGame | None = None
        if isinstance(selected, RomMRemoteGame):
            remote_game = selected
            game_name = selected.name
        else:
            source = selected.path
            if not source.is_file():
                QMessageBox.warning(self, "File not found", "The selected library file is no longer available.")
                return
            game_name = selected.name

        destination = self.destination_edit.text().strip()
        if not destination:
            QMessageBox.warning(self, "Destination required", "Enter a remote destination first.")
            return
        try:
            settings = self.settings()
            self.save_settings()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid FTP settings", str(exc))
            return

        self.progress.setValue(0)
        self.status.setText(f"Preparing {game_name}…")
        self.worker = ThreeDSTransferWorker(
            settings,
            source,
            destination,
            remote_game=remote_game,
            romm_url=self.library_source.romm_url,
            romm_token=self.library_source.api_token,
        )
        self.worker.status_changed.connect(self.status.setText)
        self.worker.progress.connect(self.worker_progress)
        self.worker.completed.connect(self.worker_completed)
        self.worker.failed.connect(self.worker_failed)
        self.worker.finished.connect(self._worker_finished)
        self._update_controls()
        self.worker.start()

    def worker_progress(self, done: int) -> None:
        selected = self._selected_game()
        if selected is None:
            return
        total = selected.size if isinstance(selected, RomMRemoteGame) else selected.path.stat().st_size if selected.path.is_file() else 0
        self.progress.setValue(int(done * 100 / total) if total else 100)

    def worker_completed(self, result: str) -> None:
        messages = {
            "copied": "File uploaded and size verified.",
            "resumed": "Partial file resumed and size verified.",
            "skipped": "Remote file already has the same size; nothing was overwritten.",
            "different": "A different-size remote file exists. No overwrite was performed.",
            "cancelled": "Transfer cancelled.",
        }
        self.status.setText(messages.get(result, result))
        if result == "different":
            QMessageBox.warning(self, "3DS file already exists", self.status.text())

    def worker_failed(self, message: str) -> None:
        self.status.setText(f"Transfer failed: {message}")

    def _worker_finished(self) -> None:
        self.worker = None
        self._update_controls()

    def cancel_transfer(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.status.setText("Cancelling…")
            self.cancel_button.setEnabled(False)

    def closeEvent(self, event) -> None:
        if self.connection_worker is not None and self.connection_worker.isRunning():
            self.connection_worker.wait(1500)
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
        super().closeEvent(event)
