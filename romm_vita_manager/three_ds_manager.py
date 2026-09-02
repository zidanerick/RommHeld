from __future__ import annotations

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
from .romm import scan_games
from .three_ds_ftp import ThreeDSFtpBackend, ThreeDSFtpSettings, join_remote_path


def default_3ds_destination(game_name: str, suffix: str) -> str:
    """Return a conservative destination for formats with documented 3DS paths."""
    if suffix.lower() == ".nds":
        return join_remote_path("/", f"roms/nds/{game_name}")
    if suffix.lower() == ".gba":
        return join_remote_path("/", f"roms/gba/{game_name}")
    return game_name


class ThreeDSTransferWorker(QThread):
    progress = Signal(int)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, settings: ThreeDSFtpSettings, source: Path, destination: str):
        super().__init__()
        self.settings = settings
        self.source = source
        self.destination = destination
        self.cancel_event = threading.Event()
        self.backend: ThreeDSFtpBackend | None = None

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            self.backend = ThreeDSFtpBackend(self.settings)
            self.backend.connect()
            result, _ = self.backend.upload(
                self.source,
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


class ThreeDSManagerDialog(QDialog):
    """3DS deployment surface for local library content and FTP configuration."""

    def __init__(self, config: dict, library_root: Path | None = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.library_root = library_root.expanduser() if library_root else None
        self.worker: ThreeDSTransferWorker | None = None
        self._connected = False

        self.setWindowTitle("Nintendo 3DS Manager")
        self.resize(960, 700)

        saved = config.get("devices", {}).get("3ds", {})
        self.host_edit = QLineEdit(str(saved.get("host", "")))
        self.port_edit = QLineEdit(str(saved.get("port", 5000)))
        self.user_edit = QLineEdit(str(saved.get("username", "anonymous")))
        self.password_edit = QLineEdit(str(saved.get("password", "")))
        from PySide6.QtWidgets import QLineEdit as _QLineEdit
        self.password_edit.setEchoMode(_QLineEdit.EchoMode.Password)
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

        self.status = QLabel("Connect to the 3DS FTP server to deploy a local game.")
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
        layout.addWidget(QLabel("Local library games:"))
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
        try:
            settings = self.settings()
            self.save_settings()
            backend = ThreeDSFtpBackend(settings)
            backend.connect()
            backend.close()
        except Exception as exc:
            self._connected = False
            self._update_controls()
            QMessageBox.warning(self, "3DS FTP connection failed", str(exc))
            return
        self._connected = True
        self.status.setText("Connected to the 3DS FTP server. Transfers use verified destination sizes and safe duplicate handling.")
        self._update_controls()

    def refresh_library(self) -> None:
        self.game_list.clear()
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
        self.destination_edit.setText(default_3ds_destination(game.path.name, game.path.suffix))
        self._update_controls()

    def _update_controls(self) -> None:
        running = bool(self.worker and self.worker.isRunning())
        selected = self.game_list.currentItem() is not None
        self.connect_button.setEnabled(not running)
        self.refresh_button.setEnabled(not running)
        self.send_button.setEnabled(self._connected and selected and not running)
        self.cancel_button.setEnabled(running)
        for widget in (self.host_edit, self.port_edit, self.user_edit, self.password_edit, self.root_edit, self.destination_edit):
            widget.setEnabled(not running)

    def send_selected(self) -> None:
        item = self.game_list.currentItem()
        if item is None:
            return
        game = item.data(256)
        if not game.path.is_file():
            QMessageBox.warning(self, "File not found", "The selected library file is no longer available.")
            return
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
        self.status.setText(f"Transferring {game.name}…")
        self.worker = ThreeDSTransferWorker(settings, game.path, destination)
        self.worker.progress.connect(self.worker_progress)
        self.worker.completed.connect(self.worker_completed)
        self.worker.failed.connect(self.worker_failed)
        self.worker.finished.connect(self._worker_finished)
        self._update_controls()
        self.worker.start()

    def worker_progress(self, done: int) -> None:
        item = self.game_list.currentItem()
        if item is None:
            return
        game = item.data(256)
        total = game.path.stat().st_size if game.path.is_file() else 0
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
        QMessageBox.critical(self, "3DS transfer failed", message)
        self._connected = False

    def _worker_finished(self) -> None:
        self.worker = None
        self._update_controls()

    def cancel_transfer(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.status.setText("Cancelling…")
            self.cancel_button.setEnabled(False)

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1500)
        super().closeEvent(event)


__all__ = ["ThreeDSManagerDialog", "default_3ds_destination"]
