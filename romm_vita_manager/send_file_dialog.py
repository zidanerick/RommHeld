from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .config import load_config, save_config
from .design_tokens import DARK, brand_for_platform
from .file_transfer import required_transfer_space, transfer_file
from .ui_components import AccentButton, SectionHeader, StatusPill, SurfaceCard
from .vita import free_space, is_vita_mount
from .vita_ftp import VitaFtpBackend, VitaFtpSettings
from .vita_paths import vita_target


PLAYSTATION_BLUE = brand_for_platform("vita").accent


def human_size(value: int) -> str:
    n = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{value} B"


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


class VitaFtpSendWorker(QThread):
    progress = Signal(int)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        settings: VitaFtpSettings,
        source: Path,
        destination: str,
        overwrite: bool = False,
    ):
        super().__init__()
        self.settings = settings
        self.source = source
        self.destination = destination
        self.overwrite = overwrite
        self.cancel_event = threading.Event()
        self.backend: VitaFtpBackend | None = None

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            self.backend = VitaFtpBackend(self.settings)
            self.backend.connect()
            result, _ = self.backend.upload(
                self.source,
                self.destination,
                overwrite=self.overwrite,
                cancel_event=self.cancel_event,
                progress=self.progress.emit,
            )
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if self.backend is not None:
                self.backend.close()


class SendFileDialog(QDialog):
    """Explicit single-file Vita transfer surface outside normal library deploys."""

    def __init__(self, vita: Path | None, parent=None):
        super().__init__(parent)
        self.vita = vita if vita is not None and is_vita_mount(vita) else None
        vita = self.vita
        self.worker: SendFileWorker | VitaFtpSendWorker | None = None
        self.overwrite = False
        self._pending_overwrite_review = False
        self._settled_status: tuple[str, str] | None = None
        self.config = load_config()
        saved_ftp = self.config.get("devices", {}).get("vita_ftp", {})

        self.setWindowTitle("Send File to PlayStation Vita")
        self.resize(840, 660)
        self.setMinimumSize(720, 560)

        header = SectionHeader(
            "Send one file to your Vita",
            "USB through VitaShell is preferred on handheld Vita systems. VitaShell FTP is available for wireless transfers and PlayStation TV.",
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

        connection_card = SurfaceCard()
        connection_card.content.addWidget(self._card_title("1 · Choose the Vita connection"))
        self.transport_combo = QComboBox()
        self.transport_combo.addItem("USB via VitaShell · Recommended", "usb")
        self.transport_combo.addItem("FTP via VitaShell · Wireless / PlayStation TV", "ftp")
        connection_card.content.addWidget(self.transport_combo)

        self.connection_help = self._secondary("")
        connection_card.content.addWidget(self.connection_help)

        self.ftp_panel = QWidget()
        ftp_form = QFormLayout(self.ftp_panel)
        ftp_form.setContentsMargins(0, 4, 0, 0)
        ftp_form.setHorizontalSpacing(12)
        ftp_form.setVerticalSpacing(8)
        self.ftp_host_edit = QLineEdit(str(saved_ftp.get("host", "")))
        self.ftp_host_edit.setPlaceholderText("IP address shown by VitaShell")
        self.ftp_port_edit = QLineEdit(str(saved_ftp.get("port", 1337)))
        self.ftp_port_edit.setPlaceholderText("1337")
        ftp_form.addRow("Vita IP", self.ftp_host_edit)
        ftp_form.addRow("Port", self.ftp_port_edit)
        connection_card.content.addWidget(self.ftp_panel)

        source_card = SurfaceCard()
        source_card.content.addWidget(self._card_title("2 · Choose the local file"))
        source_card.content.addWidget(
            self._secondary(
                "RommHeld verifies the completed file size. USB also checks available storage before the safe staged copy."
            )
        )
        source_row = QHBoxLayout()
        source_row.setSpacing(8)
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Choose a local file")
        self.source_edit.textChanged.connect(self._selection_changed)
        self.source_button = QPushButton("Choose…")
        self.source_button.clicked.connect(self.choose_source)
        source_row.addWidget(self.source_edit, 1)
        source_row.addWidget(self.source_button)
        source_card.content.addLayout(source_row)

        destination_card = SurfaceCard()
        destination_card.content.addWidget(self._card_title("3 · Choose the Vita destination"))
        destination_card.content.addWidget(
            self._secondary(
                "Enter a path inside ux0. Examples: ux0:/data/file.zip, ux0:/downloads/file.bin, or ux0:/VPK/app.vpk. Other Vita mountpoints are intentionally not exposed here."
            )
        )
        self.destination_edit = QLineEdit("ux0:/")
        self.destination_edit.textChanged.connect(self._selection_changed)
        destination_card.content.addWidget(self.destination_edit)

        activity_card = SurfaceCard()
        activity_card.content.addWidget(self._card_title("4 · Transfer"))
        self.status = QLabel("Choose a connection, file and destination.")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
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
        self.done_button = QPushButton("Done")
        self.done_button.clicked.connect(self.accept)
        close_row.addWidget(self.done_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(header)
        layout.addLayout(status_row)
        layout.addWidget(connection_card)
        layout.addWidget(source_card)
        layout.addWidget(destination_card)
        layout.addWidget(activity_card)
        layout.addStretch(1)
        layout.addLayout(close_row)

        if vita is None and self.ftp_host_edit.text().strip():
            self.transport_combo.setCurrentIndex(1)
        self.transport_combo.currentIndexChanged.connect(self._transport_changed)
        self.ftp_host_edit.textChanged.connect(self._selection_changed)
        self.ftp_port_edit.textChanged.connect(self._selection_changed)
        self._transport_changed()

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

    def _transport(self) -> str:
        return str(self.transport_combo.currentData() or "usb")

    def _transport_changed(self) -> None:
        ftp = self._transport() == "ftp"
        self.ftp_panel.setVisible(ftp)
        if ftp:
            self.connection_help.setText(
                "In VitaShell press START, set SELECT button to FTP, close Settings, then press SELECT. Enter the IP address and port VitaShell displays. VitaShell normally uses port 1337. PlayStation TV uses the FTP route."
            )
            self.device_status.set_value(
                "FTP configured" if self.ftp_host_edit.text().strip() else "FTP needs endpoint"
            )
        else:
            self.connection_help.setText(
                "In VitaShell press START, set SELECT button to USB, choose the USB device that contains ux0, close Settings, press SELECT, then connect a USB data cable."
            )
            self.device_status.set_value("Connected" if self.vita is not None else "Not mounted")
        self.overwrite = False
        self._selection_changed()

    def _ftp_settings(self) -> VitaFtpSettings:
        host = self.ftp_host_edit.text().strip()
        if not host:
            raise ValueError("Enter the IP address shown by VitaShell FTP.")
        try:
            port = int(self.ftp_port_edit.text().strip() or "1337")
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError as exc:
            raise ValueError("VitaShell FTP port must be between 1 and 65535.") from exc
        return VitaFtpSettings(host=host, port=port)

    def _save_ftp_settings(self, settings: VitaFtpSettings) -> None:
        cfg = load_config()
        devices = dict(cfg.get("devices", {}))
        devices["vita_ftp"] = {
            "host": settings.host,
            "port": settings.port,
        }
        cfg["devices"] = devices
        save_config(cfg)
        self.config = cfg

    def _set_transfer_inputs_enabled(self, enabled: bool) -> None:
        self.transport_combo.setEnabled(enabled)
        self.ftp_host_edit.setEnabled(enabled)
        self.ftp_port_edit.setEnabled(enabled)
        self.source_edit.setEnabled(enabled)
        self.source_button.setEnabled(enabled)
        self.destination_edit.setEnabled(enabled)

    def _selection_changed(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        source = Path(self.source_edit.text()).expanduser()
        destination = self.destination_edit.text().strip()
        if self._transport() == "ftp":
            endpoint_ready = bool(self.ftp_host_edit.text().strip())
            try:
                port = int(self.ftp_port_edit.text().strip() or "1337")
                endpoint_ready = endpoint_ready and 1 <= port <= 65535
            except ValueError:
                endpoint_ready = False
            ready = endpoint_ready and source.is_file() and bool(destination)
            self.device_status.set_value("FTP configured" if endpoint_ready else "FTP needs endpoint")
        else:
            ready = self.vita is not None and source.is_file() and bool(destination)
            self.device_status.set_value("Connected" if self.vita is not None else "Not mounted")
        self.send_button.setEnabled(ready)
        if ready:
            self.transfer_status.set_value("Ready")
            self.status.setText(
                f"Ready to send {source.name} ({human_size(source.stat().st_size)}) via {self._transport().upper()}."
            )
        elif self._transport() == "usb" and self.vita is None:
            self.transfer_status.set_value("Vita required")
            self.status.setText(
                "Start VitaShell USB and connect the Vita, or choose VitaShell FTP for a wireless / PlayStation TV transfer."
            )
        elif self._transport() == "ftp" and not self.ftp_host_edit.text().strip():
            self.transfer_status.set_value("Endpoint required")
            self.status.setText("Start FTP in VitaShell and enter the IP address and port it displays.")
        else:
            self.transfer_status.set_value("Waiting")
            self.status.setText("Choose a local file and Vita destination.")

    def choose_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose file")
        if path:
            self.source_edit.setText(path)

    def selected_source(self) -> Path:
        return Path(self.source_edit.text()).expanduser()

    def selected_destination(self) -> Path:
        if self.vita is None:
            raise RuntimeError("Vita is not connected through USB")
        return vita_target(self.vita, self.destination_edit.text())

    def start_transfer(self) -> None:
        try:
            source = self.selected_source()
            if not source.is_file():
                raise FileNotFoundError("Choose an existing local file.")
            destination_text = self.destination_edit.text().strip()
            if not destination_text:
                raise ValueError("Enter a Vita destination inside ux0.")
            required = source.stat().st_size

            if self._transport() == "ftp":
                settings = self._ftp_settings()
                self._save_ftp_settings(settings)
                self.worker = VitaFtpSendWorker(
                    settings,
                    source,
                    destination_text,
                    overwrite=self.overwrite,
                )
                status_text = f"Uploading {source.name} to {destination_text} through VitaShell FTP…"
            else:
                if self.vita is None or not is_vita_mount(self.vita):
                    self.vita = None
                    raise RuntimeError(
                        "The VitaShell USB mount is no longer available. Reconnect the Vita or choose VitaShell FTP."
                    )
                destination = self.selected_destination()
                available = None
                try:
                    available = free_space(self.vita)
                except OSError:
                    pass
                needed = required_transfer_space(
                    required,
                    destination,
                    overwrite=self.overwrite,
                )
                if available is not None and needed > available:
                    raise OSError(
                        f"Not enough Vita free space for the safe staged transfer. "
                        f"{human_size(needed)} is required."
                    )
                self.worker = SendFileWorker(source, destination, overwrite=self.overwrite)
                status_text = f"Copying {source.name} to {destination_text} through VitaShell USB…"

            self._settled_status = None
            self._set_transfer_inputs_enabled(False)
            self.done_button.setEnabled(False)
            self.send_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.progress.setVisible(True)
            self.progress.setValue(0)
            self.transfer_status.set_value("Transferring")
            self.status.setText(status_text)
            self.worker.progress.connect(
                lambda done: self.progress.setValue(
                    int(done * 100 / required) if required else 100
                )
            )
            self.worker.completed.connect(self.transfer_finished)
            self.worker.failed.connect(self.transfer_failed)
            self.worker.finished.connect(self._worker_finished)
            self.worker.start()
        except Exception as exc:
            self.worker = None
            self.overwrite = False
            self._pending_overwrite_review = False
            self._set_transfer_inputs_enabled(True)
            self.done_button.setEnabled(True)
            self._selection_changed()
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
            self._pending_overwrite_review = True
            self.transfer_status.set_value("Overwrite needed")
            self.status.setText("Waiting for the transfer worker to finish before overwrite review…")
            return

        message = {
            "copied": "Transfer completed and size verified.",
            "skipped": "Destination already contains the same-size file.",
            "cancelled": "Transfer cancelled. Any existing destination was preserved.",
        }.get(result, result)
        status_value = "Complete" if result in {"copied", "skipped"} else "Cancelled"
        self.status.setText(message)
        self.transfer_status.set_value(status_value)
        self._settled_status = (status_value, message)
        self.overwrite = False
        self._pending_overwrite_review = False
        if result in {"copied", "skipped"}:
            QMessageBox.information(self, "Send File", message)

    def transfer_failed(self, message: str) -> None:
        self.cancel_button.setEnabled(False)
        self.progress.setVisible(False)
        self.transfer_status.set_value("Failed")
        failure_message = "Transfer failed. Any existing destination was preserved."
        self.status.setText(failure_message)
        self._settled_status = ("Failed", failure_message)
        self.overwrite = False
        self._pending_overwrite_review = False
        QMessageBox.critical(self, "Transfer failed", message)

    def _worker_finished(self) -> None:
        review_overwrite = self._pending_overwrite_review
        self._pending_overwrite_review = False
        self.worker = None

        if review_overwrite:
            answer = QMessageBox.question(
                self,
                "File already exists",
                "The destination contains a different-size file. Overwrite it? The existing file is preserved until the replacement has uploaded and verified successfully.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.overwrite = True
                self.status.setText("Preparing verified replacement…")
                self.start_transfer()
                return
            self.overwrite = False
            self._settled_status = (
                "Ready",
                "Overwrite cancelled. The existing destination was preserved.",
            )

        self._set_transfer_inputs_enabled(True)
        self.done_button.setEnabled(True)
        self._selection_changed()
        if self._settled_status is not None:
            status_value, message = self._settled_status
            self.transfer_status.set_value(status_value)
            self.status.setText(message)
            self._settled_status = None

    def _worker_active(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def _show_transfer_in_progress(self) -> None:
        QMessageBox.information(
            self,
            "Transfer in progress",
            "Cancel the active transfer before closing this window.",
        )

    def accept(self) -> None:
        if self._worker_active():
            self._show_transfer_in_progress()
            return
        super().accept()

    def reject(self) -> None:
        if self._worker_active():
            self._show_transfer_in_progress()
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker_active():
            self._show_transfer_in_progress()
            event.ignore()
            return
        super().closeEvent(event)


__all__ = [
    "SendFileDialog",
    "SendFileWorker",
    "VitaFtpSendWorker",
    "human_size",
    "vita_target",
]
