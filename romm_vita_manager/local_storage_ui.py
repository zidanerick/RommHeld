from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
)

from .config import save_config
from .file_transfer import transfer_file
from .local_storage import resolve_destination, resolve_storage_root, storage_summary


def _human_size(value: int) -> str:
    n = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{value} B"


class StorageTransferWorker(QThread):
    progress = Signal(int)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, source: Path, destination: Path, overwrite: bool = False):
        super().__init__()
        self.source = source
        self.destination = destination
        self.overwrite = overwrite
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            result, _ = transfer_file(
                self.source,
                self.destination,
                self.cancel_event,
                progress=self.progress.emit,
                overwrite=self.overwrite,
            )
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class MountedStorageDialog(QDialog):
    """Transfer arbitrary files to a user-selected mounted storage root."""

    def __init__(self, config: dict, device_key: str, device_name: str, parent=None):
        super().__init__(parent)
        self.config = config
        self.device_key = device_key
        self.device_name = device_name
        self.worker: StorageTransferWorker | None = None
        self.overwrite = False
        self.setWindowTitle(f"{device_name} • SD / Removable Storage")
        self.resize(780, 360)

        saved = config.get("devices", {}).get(device_key, {})
        self.root_edit = QLineEdit(str(saved.get("storage_root", "")))
        browse_root = QPushButton("Browse…")
        browse_root.clicked.connect(self.choose_root)
        root_row = QHBoxLayout()
        root_row.addWidget(self.root_edit, 1)
        root_row.addWidget(browse_root)

        self.storage_status = QLabel("Choose the mounted SD/card directory.")
        self.refresh_button = QPushButton("Check Storage")
        self.refresh_button.clicked.connect(self.refresh_storage)

        self.local_edit = QLineEdit()
        choose_local = QPushButton("Choose…")
        choose_local.clicked.connect(self.choose_local)
        local_row = QHBoxLayout()
        local_row.addWidget(self.local_edit, 1)
        local_row.addWidget(choose_local)

        self.destination_edit = QLineEdit()
        self.destination_edit.setPlaceholderText("e.g. roms/gba/game.gba")
        self.send_button = QPushButton("Send File")
        self.send_button.clicked.connect(self.start_transfer)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_transfer)

        self.progress = QProgressBar()
        self.status = QLabel("Ready.")

        form = QFormLayout()
        form.addRow("Storage root:", root_row)
        form.addRow("Local file:", local_row)
        form.addRow("Destination:", self.destination_edit)

        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_button)
        buttons.addStretch()
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.send_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.storage_status)
        layout.addLayout(buttons)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)

        if self.root_edit.text().strip():
            self.refresh_storage()

    def choose_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select mounted SD/card root")
        if path:
            self.root_edit.setText(path)
            self.refresh_storage()

    def choose_local(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose file")
        if path:
            local = Path(path)
            self.local_edit.setText(str(local))
            if not self.destination_edit.text().strip():
                self.destination_edit.setText(local.name)

    def refresh_storage(self) -> None:
        try:
            root = resolve_storage_root(self.root_edit.text())
            total, free = storage_summary(root)
            if total is not None and free is not None:
                self.storage_status.setText(
                    f"Mounted: {root} • {_human_size(free)} free of {_human_size(total)}"
                )
            else:
                self.storage_status.setText(f"Mounted: {root} • free space unavailable")
            cfg = dict(self.config)
            devices = dict(cfg.get("devices", {}))
            device = dict(devices.get(self.device_key, {}))
            device["storage_root"] = str(root)
            devices[self.device_key] = device
            cfg["devices"] = devices
            save_config(cfg)
            self.config = cfg
        except Exception as exc:
            self.storage_status.setText(str(exc))

    def start_transfer(self) -> None:
        try:
            root = resolve_storage_root(self.root_edit.text())
            source = Path(self.local_edit.text()).expanduser()
            if not source.is_file():
                raise FileNotFoundError("Choose an existing local file.")
            relative = self.destination_edit.text().strip()
            if not relative:
                raise ValueError("Enter a destination path relative to the storage root.")
            destination = resolve_destination(root, relative)
            required = source.stat().st_size
            total, free = storage_summary(root)
            existing = destination.stat().st_size if destination.is_file() else 0
            needed = max(0, required - existing)
            if free is not None and needed > free:
                raise OSError(f"Not enough storage space for {_human_size(needed)}.")

            destination.parent.mkdir(parents=True, exist_ok=True)
            self.send_button.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.progress.setValue(0)
            self.status.setText(f"Transferring {_human_size(required)}…")
            self.worker = StorageTransferWorker(source, destination, overwrite=self.overwrite)
            self.worker.progress.connect(
                lambda done: self.progress.setValue(int(done * 100 / required) if required else 100)
            )
            self.worker.completed.connect(self.transfer_finished)
            self.worker.failed.connect(self.transfer_failed)
            self.worker.start()
        except Exception as exc:
            QMessageBox.warning(self, "Unable to send file", str(exc))

    def cancel_transfer(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.status.setText("Cancelling…")

    def transfer_finished(self, result: str) -> None:
        self.cancel_button.setEnabled(False)
        self.refresh_button.setEnabled(True)
        if result == "different":
            self.send_button.setEnabled(True)
            answer = QMessageBox.question(
                self,
                "File already exists",
                "The destination contains a different-size file. Overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.overwrite = True
                self.start_transfer()
            return

        self.send_button.setEnabled(True)
        message = {
            "copied": "Transfer completed and size verified.",
            "skipped": "Destination already contains the same-size file.",
            "cancelled": "Transfer cancelled.",
        }.get(result, result)
        self.status.setText(message)
        QMessageBox.information(self, "Transfer", message)

    def transfer_failed(self, message: str) -> None:
        self.send_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        QMessageBox.critical(self, "Transfer failed", message)
