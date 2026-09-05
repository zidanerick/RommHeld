from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from .config import save_config
from .design_tokens import DARK, brand_for_platform
from .file_transfer import required_transfer_space, transfer_file
from .local_storage import resolve_destination, resolve_storage_root, storage_summary
from .ui_components import AccentButton, SectionHeader, StatusPill, SurfaceCard


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
    """Transfer arbitrary files to a validated mounted storage root."""

    def __init__(self, config: dict, device_key: str, device_name: str, parent=None):
        super().__init__(parent)
        self.config = config
        self.device_key = device_key
        self.device_name = device_name
        self.worker: StorageTransferWorker | None = None
        self.overwrite = False
        self.accent = brand_for_platform(device_key).accent

        self.setWindowTitle(f"{device_name} · Removable Storage")
        self.resize(840, 590)
        self.setMinimumSize(720, 520)

        saved = config.get("devices", {}).get(device_key, {})

        header = SectionHeader(
            f"Manage {device_name} storage",
            "Choose the mounted card or removable-storage root first, then send a file to an explicit path inside it. RommHeld will not write outside the selected root.",
        )

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self.storage_pill = StatusPill("Storage", "Not checked")
        self.transfer_pill = StatusPill("Transfer", "Waiting")
        status_row.addWidget(self.storage_pill)
        status_row.addWidget(self.transfer_pill)
        status_row.addStretch(1)

        storage_card = SurfaceCard()
        storage_card.content.addWidget(self._card_title("1 · Select removable storage"))
        storage_card.content.addWidget(
            self._secondary(
                "Select the mounted SD card or removable-storage root. The validated root is remembered for this device."
            )
        )
        root_row = QHBoxLayout()
        root_row.setSpacing(8)
        self.root_edit = QLineEdit(str(saved.get("storage_root", "")))
        self.root_edit.setPlaceholderText("Mounted storage root")
        self.root_edit.textChanged.connect(self._selection_changed)
        browse_root = QPushButton("Choose…")
        browse_root.clicked.connect(self.choose_root)
        self.refresh_button = QPushButton("Check storage")
        self.refresh_button.clicked.connect(self.refresh_storage)
        root_row.addWidget(self.root_edit, 1)
        root_row.addWidget(browse_root)
        root_row.addWidget(self.refresh_button)
        storage_card.content.addLayout(root_row)

        self.storage_status = QLabel("Choose the mounted SD/card directory.")
        self.storage_status.setWordWrap(True)
        self.storage_status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        storage_card.content.addWidget(self.storage_status)

        file_card = SurfaceCard()
        file_card.content.addWidget(self._card_title("2 · Choose a file and destination"))
        file_card.content.addWidget(
            self._secondary(
                "The destination is relative to the selected storage root, for example roms/gba/game.gba or _nds/TWiLightMenu/extras/file.bin."
            )
        )

        local_row = QHBoxLayout()
        local_row.setSpacing(8)
        self.local_edit = QLineEdit()
        self.local_edit.setPlaceholderText("Choose a local file")
        self.local_edit.textChanged.connect(self._selection_changed)
        choose_local = QPushButton("Choose…")
        choose_local.clicked.connect(self.choose_local)
        local_row.addWidget(self.local_edit, 1)
        local_row.addWidget(choose_local)
        file_card.content.addLayout(local_row)

        self.destination_edit = QLineEdit()
        self.destination_edit.setPlaceholderText("Destination relative to storage root")
        self.destination_edit.textChanged.connect(self._selection_changed)
        file_card.content.addWidget(self.destination_edit)

        activity_card = SurfaceCard()
        activity_card.content.addWidget(self._card_title("3 · Transfer"))
        self.status = QLabel("Check the storage root, then choose a file and destination.")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        activity_card.content.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        activity_card.content.addWidget(self.progress)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_button = QPushButton("Cancel transfer")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_transfer)
        self.send_button = AccentButton("Send file", self.accent)
        self.send_button.setEnabled(False)
        self.send_button.clicked.connect(self.start_transfer)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.send_button)
        activity_card.content.addLayout(buttons)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close = QPushButton("Done")
        close.clicked.connect(self.accept)
        close_row.addWidget(close)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(header)
        layout.addLayout(status_row)
        layout.addWidget(storage_card)
        layout.addWidget(file_card)
        layout.addWidget(activity_card)
        layout.addStretch(1)
        layout.addLayout(close_row)

        if self.root_edit.text().strip():
            self.refresh_storage()
        else:
            self._selection_changed()

    def _card_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"color:{DARK.text_primary};font-size:15px;font-weight:700;background:transparent;"
        )
        return label

    def _secondary(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{DARK.text_secondary};background:transparent;")
        return label

    def _selection_changed(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        source = Path(self.local_edit.text()).expanduser()
        root_ready = False
        try:
            resolve_storage_root(self.root_edit.text())
            root_ready = True
        except Exception:
            pass
        ready = root_ready and source.is_file() and bool(self.destination_edit.text().strip())
        self.send_button.setEnabled(ready)
        if ready:
            self.transfer_pill.set_value("Ready")
            self.status.setText(
                f"Ready to send {source.name} ({_human_size(source.stat().st_size)})."
            )
        elif root_ready:
            self.transfer_pill.set_value("Waiting")
        else:
            self.transfer_pill.set_value("Storage required")

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
                    f"{root} · {_human_size(free)} free of {_human_size(total)}"
                )
                self.storage_pill.set_value(f"{_human_size(free)} free")
            else:
                self.storage_status.setText(f"{root} · free space unavailable")
                self.storage_pill.set_value("Mounted")

            cfg = dict(self.config)
            devices = dict(cfg.get("devices", {}))
            device = dict(devices.get(self.device_key, {}))
            device["storage_root"] = str(root)
            devices[self.device_key] = device
            cfg["devices"] = devices
            save_config(cfg)
            self.config = cfg
            self._selection_changed()
        except Exception as exc:
            self.storage_status.setText(str(exc))
            self.storage_pill.set_value("Unavailable")
            self.send_button.setEnabled(False)

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
            _, free = storage_summary(root)
            needed = required_transfer_space(
                required,
                destination,
                overwrite=self.overwrite,
            )
            if free is not None and needed > free:
                raise OSError(
                    f"Not enough storage space for the safe staged transfer. "
                    f"{_human_size(needed)} is required."
                )

            destination.parent.mkdir(parents=True, exist_ok=True)
            self.send_button.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.progress.setVisible(True)
            self.progress.setValue(0)
            self.transfer_pill.set_value("Transferring")
            self.status.setText(
                f"Copying {source.name} to {relative} · {_human_size(required)}"
            )
            self.worker = StorageTransferWorker(
                source, destination, overwrite=self.overwrite
            )
            self.worker.progress.connect(
                lambda done: self.progress.setValue(
                    int(done * 100 / required) if required else 100
                )
            )
            self.worker.completed.connect(self.transfer_finished)
            self.worker.failed.connect(self.transfer_failed)
            self.worker.start()
        except Exception as exc:
            self.overwrite = False
            self._selection_changed()
            QMessageBox.warning(self, "Unable to send file", str(exc))

    def cancel_transfer(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.transfer_pill.set_value("Cancelling")
            self.status.setText("Cancelling transfer…")

    def transfer_finished(self, result: str) -> None:
        self.cancel_button.setEnabled(False)
        self.refresh_button.setEnabled(True)
        self.progress.setVisible(False)
        if result == "different":
            self.send_button.setEnabled(True)
            self.transfer_pill.set_value("Needs confirmation")
            answer = QMessageBox.question(
                self,
                "File already exists",
                "The destination contains a different-size file. Overwrite it? The existing file is kept until the replacement has copied successfully.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.overwrite = True
                self.start_transfer()
            else:
                self.overwrite = False
                self._selection_changed()
            return

        message = {
            "copied": "Transfer completed and size verified.",
            "skipped": "Destination already contains the same-size file.",
            "cancelled": "Transfer cancelled. Any existing destination was preserved.",
        }.get(result, result)
        self.status.setText(message)
        self.transfer_pill.set_value(
            {
                "copied": "Complete",
                "skipped": "Already present",
                "cancelled": "Cancelled",
            }.get(result, "Finished")
        )
        self.overwrite = False
        self._selection_changed()
        QMessageBox.information(self, "Transfer", message)

    def transfer_failed(self, message: str) -> None:
        self.refresh_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress.setVisible(False)
        self.transfer_pill.set_value("Failed")
        self.status.setText("Transfer failed. An existing destination was preserved.")
        self.overwrite = False
        self._selection_changed()
        QMessageBox.critical(self, "Transfer failed", message)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(
                self,
                "Transfer in progress",
                "Cancel the current transfer and let it finish before closing this window.",
            )
            event.ignore()
            return
        super().closeEvent(event)
