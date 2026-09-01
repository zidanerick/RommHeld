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
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
)

from .config import load_config, save_config
from .file_transfer import transfer_file
from .three_ds_ftp import ThreeDSFtpBackend, ThreeDSFtpSettings, join_remote_path
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


class SendFileDialog(QDialog):
    def __init__(self, vita: Path | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Send File to Vita")
        self.resize(760, 260)
        self.vita = vita
        self.worker: SendFileWorker | None = None
        self.overwrite = False

        self.source_edit = QLineEdit()
        source_button = QPushButton("Choose…")
        source_button.clicked.connect(self.choose_source)
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_edit, 1)
        source_row.addWidget(source_button)

        self.destination_edit = QLineEdit("ux0:/")
        self.status = QLabel("Choose a file and an explicit Vita destination.")
        self.progress = QProgressBar()

        form = QFormLayout()
        form.addRow("Local file:", source_row)
        form.addRow("Remote file path:", self.destination_edit)

        self.send_button = QPushButton("Send File")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.send_button.clicked.connect(self.start_transfer)
        self.cancel_button.clicked.connect(self.cancel_transfer)

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
                raise OSError(f"Not enough Vita free space for {_human_size(needed)}.")
            self.send_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.status.setText(f"Transferring {_human_size(required)}…")
            self.progress.setValue(0)
            self.worker = SendFileWorker(source, destination, overwrite=self.overwrite)
            self.worker.progress.connect(lambda done: self.progress.setValue(int(done * 100 / required) if required else 100))
            self.worker.completed.connect(self.transfer_finished)
            self.worker.failed.connect(self.transfer_failed)
            self.worker.start()
        except Exception as exc:
            QMessageBox.warning(self, "Unable to send file", str(exc))

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
                self.start_transfer()
            return
        self.status.setText({
            "copied": "Transfer completed and size verified.",
            "skipped": "Destination already contains the same-size file.",
            "cancelled": "Transfer cancelled.",
        }.get(result, result))
        QMessageBox.information(self, "Send File", self.status.text())
        self.accept()

    def transfer_failed(self, message: str):
        self.send_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        QMessageBox.critical(self, "Transfer failed", message)


class ThreeDSWorker(QThread):
    connected = Signal(str)
    listed = Signal(object)
    progress = Signal(int)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, settings: ThreeDSFtpSettings, action: str, path: str = "", local_path: Path | None = None):
        super().__init__()
        self.settings = settings
        self.action = action
        self.path = path
        self.local_path = local_path
        self.cancel_event = threading.Event()
        self.backend: ThreeDSFtpBackend | None = None

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        try:
            self.backend = ThreeDSFtpBackend(self.settings)
            self.backend.connect()
            if self.action == "connect":
                self.connected.emit("Connected to 3DS FTP")
                return
            if self.action == "list":
                self.list_remote()
                return
            if self.action == "upload":
                if self.local_path is None:
                    raise RuntimeError("No local file selected.")
                result, _ = self.backend.upload(
                    self.local_path,
                    self.path,
                    cancel_event=self.cancel_event,
                    progress=self.progress.emit,
                )
                self.completed.emit(result)
                return
            raise ValueError(f"Unknown 3DS action: {self.action}")
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if self.backend:
                self.backend.close()

    def list_remote(self):
        assert self.backend is not None
        self.listed.emit(self.backend.list_directory(self.path or "/"))


class ThreeDSFtpDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.worker: ThreeDSWorker | None = None
        self.current_dir = "/"
        self.setWindowTitle("Nintendo 3DS FTP")
        self.resize(880, 600)

        saved = config.get("devices", {}).get("3ds", {})
        self.host_edit = QLineEdit(str(saved.get("host", "")))
        self.port_edit = QLineEdit(str(saved.get("port", 5000)))
        self.user_edit = QLineEdit(str(saved.get("username", "anonymous")))
        self.password_edit = QLineEdit(str(saved.get("password", "")))
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.remote_root_edit = QLineEdit(str(saved.get("remote_root", "/")))
        self.remote_root_edit.textChanged.connect(self.remote_root_changed)

        self.connect_button = QPushButton("Connect")
        self.refresh_button = QPushButton("Refresh")
        self.up_button = QPushButton("Up")
        self.refresh_button.setEnabled(False)
        self.up_button.setEnabled(False)
        self.connect_button.clicked.connect(self.connect_3ds)
        self.refresh_button.clicked.connect(self.refresh_listing)
        self.up_button.clicked.connect(self.go_up)

        self.local_edit = QLineEdit()
        local_button = QPushButton("Choose…")
        local_button.clicked.connect(self.choose_local)
        local_row = QHBoxLayout()
        local_row.addWidget(self.local_edit, 1)
        local_row.addWidget(local_button)

        self.remote_file_edit = QLineEdit()
        self.send_button = QPushButton("Send File")
        self.send_button.setEnabled(False)
        self.send_button.clicked.connect(self.send_file)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.enter_directory)
        self.status = QLabel("Enter the FTP details shown by the 3DS FTP server.")
        self.progress = QProgressBar()

        form = QFormLayout()
        form.addRow("Host:", self.host_edit)
        form.addRow("Port:", self.port_edit)
        form.addRow("Username:", self.user_edit)
        form.addRow("Password:", self.password_edit)
        form.addRow("Remote root:", self.remote_root_edit)
        form.addRow("Local file:", local_row)
        form.addRow("Remote file:", self.remote_file_edit)

        nav = QHBoxLayout()
        nav.addWidget(self.connect_button)
        nav.addWidget(self.refresh_button)
        nav.addWidget(self.up_button)
        nav.addStretch()
        nav.addWidget(self.send_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(nav)
        layout.addWidget(QLabel("Remote directory:"))
        layout.addWidget(self.list_widget, 1)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        layout.addWidget(close)

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
            remote_root=self.remote_root_edit.text().strip() or "/",
        )

    def save_settings(self):
        cfg = dict(self.config)
        devices = dict(cfg.get("devices", {}))
        devices["3ds"] = {
            "host": self.host_edit.text().strip(),
            "port": int(self.port_edit.text()),
            "username": self.user_edit.text().strip() or "anonymous",
            "password": self.password_edit.text(),
            "remote_root": self.remote_root_edit.text().strip() or "/",
        }
        cfg["devices"] = devices
        save_config(cfg)
        self.config = cfg

    def connect_3ds(self):
        try:
            settings = self.settings()
            self.save_settings()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid FTP settings", str(exc))
            return
        self.start_worker(ThreeDSWorker(settings, "connect"))

    def refresh_listing(self):
        try:
            settings = self.settings()
            self.start_worker(ThreeDSWorker(settings, "list", self.current_dir))
        except Exception as exc:
            QMessageBox.warning(self, "Unable to browse 3DS", str(exc))

    def start_worker(self, worker: ThreeDSWorker):
        if self.worker and self.worker.isRunning():
            return
        self.worker = worker
        self.connect_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.send_button.setEnabled(False)
        worker.connected.connect(self.worker_connected)
        worker.listed.connect(self.worker_listed)
        worker.progress.connect(self.worker_progress)
        worker.completed.connect(self.worker_completed)
        worker.failed.connect(self.worker_failed)
        worker.start()

    def worker_connected(self, message: str):
        self.status.setText(message)
        self.refresh_button.setEnabled(True)
        self.up_button.setEnabled(self.current_dir != "/")
        self.send_button.setEnabled(Path(self.local_edit.text()).is_file())
        self.refresh_listing()

    def worker_listed(self, entries: object):
        self.list_widget.clear()
        for entry in entries:
            item = QListWidgetItem(
                f"{'[DIR] ' if entry['type'] == 'dir' else ''}{entry['name']}"
                + ("" if entry['type'] == 'dir' else f"  ({_human_size(int(entry['size']))})")
            )
            item.setData(256, entry)
            self.list_widget.addItem(item)
        self.status.setText(f"{self.current_dir} • {len(entries)} entries")
        self.refresh_button.setEnabled(True)
        self.up_button.setEnabled(self.current_dir != "/")
        self.send_button.setEnabled(Path(self.local_edit.text()).is_file())

    def worker_progress(self, done: int):
        source = Path(self.local_edit.text())
        total = source.stat().st_size if source.is_file() else 0
        self.progress.setValue(int(done * 100 / total) if total else 100)

    def worker_completed(self, result: str):
        self.refresh_button.setEnabled(True)
        self.send_button.setEnabled(True)
        self.progress.setValue(100)
        self.status.setText({
            "copied": "File uploaded and size verified.",
            "resumed": "Upload resumed and size verified.",
            "skipped": "Remote file already has the same size.",
            "different": "Remote file exists with a different size.",
            "cancelled": "Upload cancelled.",
        }.get(result, result))
        QMessageBox.information(self, "3DS FTP", self.status.text())

    def worker_failed(self, message: str):
        self.connect_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.send_button.setEnabled(True)
        QMessageBox.critical(self, "3DS FTP error", message)

    def choose_local(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose file")
        if path:
            self.local_edit.setText(path)
            self.send_button.setEnabled(bool(self.worker and not self.worker.isRunning()))

    def remote_root_changed(self, text: str):
        self.current_dir = text.strip() or "/"

    def enter_directory(self, item: QListWidgetItem):
        entry = item.data(256)
        if not isinstance(entry, dict) or entry.get("type") != "dir":
            return
        self.current_dir = join_remote_path(self.current_dir, str(entry["name"]))
        self.remote_root_edit.setText(self.current_dir)
        self.refresh_listing()

    def go_up(self):
        if self.current_dir == "/":
            return
        self.current_dir = str(Path(self.current_dir).parent).replace("\\", "/") or "/"
        self.remote_root_edit.setText(self.current_dir)
        self.refresh_listing()

    def send_file(self):
        local = Path(self.local_edit.text()).expanduser()
        if not local.is_file():
            QMessageBox.warning(self, "File not found", "Choose an existing local file first.")
            return
        remote_name = self.remote_file_edit.text().strip() or local.name
        try:
            settings = self.settings()
            self.save_settings()
            remote = join_remote_path(self.current_dir, remote_name)
        except Exception as exc:
            QMessageBox.warning(self, "Invalid destination", str(exc))
            return
        self.progress.setValue(0)
        self.start_worker(ThreeDSWorker(settings, "upload", remote, local))


class MainWindow(BaseMainWindow):
    def __init__(self, config: dict):
        super().__init__(config)
        self.send_file_button = QPushButton("Send File")
        self.three_ds_button = QPushButton("3DS FTP")
        self.send_file_button.clicked.connect(self.open_send_file)
        self.three_ds_button.clicked.connect(self.open_3ds)
        top = self.centralWidget().layout().itemAt(0).layout()
        top.insertWidget(top.count() - 2, self.send_file_button)
        top.insertWidget(top.count() - 2, self.three_ds_button)

    def open_send_file(self):
        if self.vita is None:
            QMessageBox.warning(self, "No Vita detected", "Connect the Vita in VitaShell USB mode first.")
            return
        SendFileDialog(self.vita, self).exec()

    def open_3ds(self):
        ThreeDSFtpDialog(self.config, self).exec()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("RommHeld")
    app.setApplicationVersion("0.8")
    config = load_config()
    if not config.get("setup_complete"):
        wizard = SetupWizard(config)
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return
        config = load_config()
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
