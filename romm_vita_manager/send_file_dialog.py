from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal
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

from .design_tokens import DARK, brand_for_platform
from .file_transfer import transfer_file
from .ui_components import AccentButton, SectionHeader, StatusPill, SurfaceCard
from .vita import free_space


PLAYSTATION_BLUE = brand_for_platform("vita").accent


def human_size(value: int) -> str:
    n = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{value} B"


def vita_target(vita: Path, remote_path: str) -> Path:
    raw = remote_path.strip().replace("\\", "/")
    if raw.startswith("ux0:/"):
        raw = raw.removeprefix("ux0:/")
    elif raw == "ux0":
        raw = ""
    elif raw.startswith("ux0/"):
        raw = raw.removeprefix("ux0/")
    base = (vita / "ux0").resolve()
    target = (base / Path(raw)).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Destination must remain inside the Vita ux0 filesystem.") from exc
    return target


class SendFileWorker(QThread):
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


class SendFileDialog(QDialog):
    """Explicit single-file Vita transfer surface outside normal library deploys."""

    def __init__(self, vita: Path | None, parent=None):
        super().__init__(parent)
        self.vita = vita
        self.worker: SendFileWorker | None = None
        self.overwrite = False

        self.setWindowTitle("Send File to PlayStation Vita")
        self.resize(820, 500)
        self.setMinimumSize(700, 440)

        header = SectionHeader(
            "Send one file to your Vita",
            "Use this for files outside the normal RommHeld library workflow. The destination is always constrained to the mounted ux0 filesystem.",
        )

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self.device_status = StatusPill(
            "Vita", "Connected" if vita is not None else "Not mounted"
        )
        self.transfer_status = StatusPill("Transfer", "Ready")
        status_row.addWidget(self.device_status)
        status_row.addWidget(self.transfer_status)
        status_row.addStretch(1)

        source_card = SurfaceCard()
        source_card.content.addWidget(self._card_title("1 · Choose the local file"))
        source_card.content.addWidget(
            self._secondary(
                "RommHeld checks the source size and available Vita space before starting the copy."
            )
        )
        source_row = QHBoxLayout()
        source_row.setSpacing(8)
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Choose a local file")
        self.source_edit.textChanged.connect(self._selection_changed)
        source_button = QPushButton("Choose…")
        source_button.clicked.connect(self.choose_source)
        source_row.addWidget(self.source_edit, 1)
        source_row.addWidget(source_button)
        source_card.content.addLayout(source_row)

        destination_card = SurfaceCard()
        destination_card.content.addWidget(self._card_title("2 · Choose the Vita destination"))
        destination_card.content.addWidget(
            self._secondary(
                "Enter a path inside ux0. Examples: ux0:/data/file.zip, ux0:/downloads/file.bin, or ux0:/VPK/app.vpk."
            )
        )
        self.destination_edit = QLineEdit("ux0:/")
        self.destination_edit.textChanged.connect(self._selection_changed)
        destination_card.content.addWidget(self.destination_edit)

        activity_card = SurfaceCard()
        activity_card.content.addWidget(self._card_title("3 · Transfer"))
        self.status = QLabel(
            "Choose a file and an explicit Vita destination."
            if vita is not None
            else "Connect the Vita in VitaShell USB mode before starting a transfer."
        )
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(
            self.status.textInteractionFlags() | self.status.textInteractionFlags().TextSelectableByMouse
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
        self.send_button = AccentButton("Send file", PLAYSTATION_BLUE)
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
        layout.addWidget(source_card)
        layout.addWidget(destination_card)
        layout.addWidget(activity_card)
        layout.addStretch(1)
        layout.addLayout(close_row)

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
        source = Path(self.source_edit.text()).expanduser()
        destination = self.destination_edit.text().strip()
        ready = self.vita is not None and source.is_file() and bool(destination)
        self.send_button.setEnabled(ready)
        if self.vita is None:
            self.transfer_status.set_value("Vita required")
        elif source.is_file() and destination:
            self.transfer_status.set_value("Ready")
            self.status.setText(
                f"Ready to send {source.name} ({human_size(source.stat().st_size)})."
            )
        else:
            self.transfer_status.set_value("Waiting")

    def choose_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose file")
        if path:
            self.source_edit.setText(path)

    def selected_source(self) -> Path:
        return Path(self.source_edit.text()).expanduser()

    def selected_destination(self) -> Path:
        if self.vita is None:
            raise RuntimeError("Vita is not connected")
        return vita_target(self.vita, self.destination_edit.text())

    def start_transfer(self) -> None:
        try:
            source = self.selected_source()
            if not source.is_file():
                raise FileNotFoundError("Choose an existing local file.")
            destination = self.selected_destination()
            required = source.stat().st_size
            available = None
            try:
                available = free_space(self.vita) if self.vita else None
            except OSError:
                pass
            existing_size = destination.stat().st_size if destination.is_file() else 0
            needed = max(0, required - existing_size)
            if available is not None and needed > available:
                raise OSError(f"Not enough Vita free space for {human_size(needed)}.")

            self.send_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.progress.setVisible(True)
            self.progress.setValue(0)
            self.transfer_status.set_value("Transferring")
            self.status.setText(
                f"Copying {source.name} to {self.destination_edit.text().strip()}…"
            )
            self.worker = SendFileWorker(source, destination, overwrite=self.overwrite)
            self.worker.progress.connect(
                lambda done: self.progress.setValue(
                    int(done * 100 / required) if required else 100
                )
            )
            self.worker.completed.connect(self.transfer_finished)
            self.worker.failed.connect(self.transfer_failed)
            self.worker.start()
        except Exception as exc:
            QMessageBox.warning(self, "Unable to send file", str(exc))

    def cancel_transfer(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self.transfer_status.set_value("Cancelling")
            self.status.setText("Cancelling transfer…")

    def transfer_finished(self, result: str) -> None:
        self.cancel_button.setEnabled(False)
        self.progress.setVisible(False)
        if result == "different":
            self.transfer_status.set_value("Overwrite needed")
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
            else:
                self._selection_changed()
            return

        message = {
            "copied": "Transfer completed and size verified.",
            "skipped": "Destination already contains the same-size file.",
            "cancelled": "Transfer cancelled.",
        }.get(result, result)
        self.status.setText(message)
        self.transfer_status.set_value(
            "Complete" if result in {"copied", "skipped"} else "Cancelled"
        )
        self._selection_changed()
        if result in {"copied", "skipped"}:
            QMessageBox.information(self, "Send File", message)

    def transfer_failed(self, message: str) -> None:
        self.cancel_button.setEnabled(False)
        self.progress.setVisible(False)
        self.transfer_status.set_value("Failed")
        self.status.setText("Transfer failed.")
        self._selection_changed()
        QMessageBox.critical(self, "Transfer failed", message)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(
                self,
                "Transfer in progress",
                "Cancel the active transfer before closing this window.",
            )
            event.ignore()
            return
        super().closeEvent(event)


__all__ = ["SendFileDialog", "SendFileWorker", "human_size", "vita_target"]
