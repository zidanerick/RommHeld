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

from .config import DEFAULT_ROMM_ROOT, load_config
from .file_transfer import transfer_file
from .ui import MainWindow as BaseMainWindow, SetupWizard
from .vita import find_vita_mounts, free_space


def _human_size(value: int) -> str:
    n = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{value} B"


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
        self.status = QLabel("Choose a file and a destination on the connected Vita.")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)

        row = QHBoxLayout()
        row.addWidget(self.source_edit, 1)
        row.addWidget(source_button)

        form = QFormLayout()
        form.addRow("Local file:", row)
        form.addRow("Remote path:", self.destination_edit)

        self.send_button = QPushButton("Send File")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.send_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.send_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addLayout(buttons)

    def choose_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose file")
        if path:
            self.source_edit.setText(path)

    def selected_source(self) -> Path:
        return Path(self.source_edit.text()).expanduser()

    def selected_destination(self) -> Path:
        text = self.destination_edit.text().strip()
        if text.startswith("ux0:/"):
            text = text.removeprefix("ux0:/")
        text = text.lstrip("/")
        return (self.vita or Path("/")) / text


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

        dialog = SendFileDialog(self.vita, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        source = dialog.selected_source()
        if not source.is_file():
            QMessageBox.warning(self, "File not found", "Choose an existing local file.")
            return

        destination = dialog.selected_destination()
        if not destination.parent.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)

        required = source.stat().st_size
        try:
            available = free_space(self.vita)
        except OSError:
            available = None
        if available is not None and destination.stat().st_size if destination.exists() else False:
            pass
        if available is not None and required > available:
            QMessageBox.warning(
                self,
                "Not enough free space",
                f"The selected file requires {_human_size(required)} but the Vita reports only {_human_size(available)} free.",
            )
            return

        worker = SendFileWorker(source, destination)
        worker.progress.connect(lambda done: dialog.progress.setValue(int(done * 100 / required) if required else 100))
        worker.status.connect(dialog.status.setText)
        worker.completed.connect(lambda result: self._send_file_finished(dialog, source, destination, result))
        worker.failed.connect(lambda message: QMessageBox.critical(dialog, "Transfer failed", message))
        dialog.send_button.setEnabled(False)
        dialog.cancel_button.setEnabled(True)
        dialog.cancel_button.clicked.disconnect()
        dialog.cancel_button.clicked.connect(worker.cancel)
        dialog.show()
        self.send_file_worker = worker
        worker.start()

    def _send_file_finished(self, dialog, source, destination, result):
        dialog.cancel_button.setEnabled(False)
        if result == "copied":
            dialog.status.setText(f"Transferred {_human_size(source.stat().st_size)} successfully.")
        elif result == "skipped":
            dialog.status.setText("Destination already contains the same-size file. Nothing copied.")
        else:
            dialog.status.setText("Transfer cancelled.")
        QMessageBox.information(dialog, "Send File", dialog.status.text())
        dialog.accept()


class SendFileWorker(QThread):
    progress = Signal(int)
    status = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, source: Path, destination: Path):
        super().__init__()
        self.source = source
        self.destination = destination
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        try:
            total = self.source.stat().st_size
            self.status.emit(f"Transferring {_human_size(total)}…")
            result, written = transfer_file(
                self.source,
                self.destination,
                self.cancel_event,
                progress=lambda done: self.progress.emit(done),
            )
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


def main() -> None:
    import sys
    from PySide6.QtWidgets import QApplication

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
