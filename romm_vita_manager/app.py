from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
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

from .config import load_config
from .file_transfer import transfer_file
from .ui import MainWindow as BaseMainWindow, SetupWizard
from .vita import free_space


def _human_size(value: int) -> str:
    n = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{value} B"


def _vita_target(vita: Path, remote_path: str) -> Path:
    """Resolve an explicit ux0:/ path beneath the mounted Vita's ux0 directory."""
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


class SendFileDialog(QDialog):
    def __init__(self, vita: Path | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Send File")
        self.resize(720, 220)
        self.vita = vita

        self.source_edit = QLineEdit()
        source_button = QPushButton("Choose…")
        source_button.clicked.connect(self.choose_source)

        self.destination_edit = QLineEdit("ux0:/")
        self.status = QLabel("Choose a file and an explicit destination on the connected Vita.")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)

        row = QHBoxLayout()
        row.addWidget(self.source_edit, 1)
        row.addWidget(source_button)

        form = QFormLayout()
        form.addRow("Local file:", row)
        form.addRow("Remote file path:", self.destination_edit)

        self.send_button = QPushButton("Send File")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.send_button)
        layout.addLayout(buttons)

        self.send_button.clicked.connect(self.start_transfer)
        self.cancel_button.clicked.connect(self.cancel_transfer)
        self.worker: SendFileWorker | None = None
        self.overwrite = False

    def choose_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose file")
        if path:
            self.source_edit.setText(path)

    def selected_source(self) -> Path:
        return Path(self.source_edit.text()).expanduser()

    def selected_destination(self) -> Path:
        if self.vita is None:
            raise RuntimeError("Vita is not connected")
        return _vita_target(self.vita, self.destination_edit.text())

    def start_transfer(self):
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
                raise OSError(
                    f"The selected file requires {_human_size(needed)} of additional space, "
                    f"but the Vita reports {_human_size(available)} free."
                )

            self._run_transfer(source, destination)
        except Exception as exc:
            QMessageBox.warning(self, "Unable to send file", str(exc))

    def _run_transfer(self, source: Path, destination: Path):
        self.send_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status.setText(f"Transferring {_human_size(source.stat().st_size)}…")
        self.progress.setValue(0)
        self.worker = SendFileWorker(source, destination, overwrite=self.overwrite)
        total = source.stat().st_size
        self.worker.progress.connect(
            lambda done: self.progress.setValue(int(done * 100 / total) if total else 100)
        )
        self.worker.completed.connect(self.transfer_finished)
        self.worker.failed.connect(self.transfer_failed)
        self.worker.start()

    def cancel_transfer(self):
        if self.worker:
            self.worker.cancel()
            self.status.setText("Cancelling…")

    def transfer_finished(self, result: str):
        self.cancel_button.setEnabled(False)
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
                try:
                    source = self.selected_source()
                    self._run_transfer(source, self.selected_destination())
                except Exception as exc:
                    QMessageBox.warning(self, "Unable to overwrite file", str(exc))
            return
        if result == "copied":
            self.status.setText("Transfer completed and size verified.")
        elif result == "skipped":
            self.status.setText("Destination already contains the same-size file.")
        else:
            self.status.setText("Transfer cancelled.")
        QMessageBox.information(self, "Send File", self.status.text())
        self.accept()

    def transfer_failed(self, message: str):
        self.send_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        QMessageBox.critical(self, "Transfer failed", message)


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

    def cancel(self):
        self.cancel_event.set()

    def run(self):
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


class MainWindow(BaseMainWindow):
    def __init__(self, config: dict):
        super().__init__(config)
        self.send_file_button = QPushButton("Send File")
        self.send_file_button.clicked.connect(self.open_send_file)
        top = self.centralWidget().layout().itemAt(0).layout()
        top.insertWidget(top.count() - 1, self.send_file_button)

    def open_send_file(self):
        if self.vita is None:
            QMessageBox.warning(self, "No Vita detected", "Connect the Vita in VitaShell USB mode first.")
            return
        SendFileDialog(self.vita, self).exec()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("RommHeld")
    app.setApplicationVersion("0.7")
    config = load_config()
    if not config.get("setup_complete"):
        wizard = SetupWizard(config)
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return
        config = load_config()
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())
