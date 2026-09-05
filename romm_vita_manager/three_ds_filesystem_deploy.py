from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from .design_tokens import DARK, brand_for_platform
from .library_sources import get_library_source
from .romm_remote import RomMRemoteGame, download_rom
from .three_ds_ftp import ThreeDSFtpSettings
from .three_ds_manager import ThreeDSTransferWorker
from .three_ds_storage import ThreeDSMountedStorageBackend, configured_3ds_storage_root
from .three_ds_targets import default_destination
from .ui_components import AccentButton, SectionHeader, StatusPill, SurfaceCard


NINTENDO_RED = brand_for_platform("3ds").accent


class ThreeDSMountedTransferWorker(QThread):
    progress = Signal(int)
    status_changed = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        root: Path,
        destination: str,
        *,
        remote_game: RomMRemoteGame,
        romm_url: str,
        romm_token: str,
        overwrite: bool = False,
    ):
        super().__init__()
        self.root = root
        self.destination = destination
        self.remote_game = remote_game
        self.romm_url = romm_url
        self.romm_token = romm_token
        self.overwrite = overwrite
        self.cancel_event = threading.Event()
        self._temporary_path: Path | None = None

    def cancel(self) -> None:
        self.cancel_event.set()

    def _resolve_source(self) -> Path:
        if not self.romm_url.strip() or not self.romm_token.strip():
            raise ValueError("RomM server credentials are not configured.")
        handle = tempfile.NamedTemporaryFile(
            prefix="rommheld-3ds-sd-",
            suffix=Path(self.remote_game.filename).suffix,
            delete=False,
        )
        handle.close()
        self._temporary_path = Path(handle.name)
        self.status_changed.emit(f"Downloading {self.remote_game.name} from RomM…")
        return download_rom(
            self.romm_url,
            self.romm_token,
            self.remote_game,
            self._temporary_path,
            cancel_event=self.cancel_event,
            progress=lambda done, _total: self.progress.emit(done),
        )

    def run(self) -> None:
        try:
            if self.cancel_event.is_set():
                self.completed.emit("cancelled")
                return

            backend = ThreeDSMountedStorageBackend(self.root)
            source: Path | None = None
            expected_size = int(self.remote_game.size)
            if expected_size <= 0:
                source = self._resolve_source()
                expected_size = source.stat().st_size

            self.status_changed.emit(
                f"Checking {self.remote_game.name} on the mounted Nintendo 3DS SD card…"
            )
            current_size = backend.remote_size(self.destination)
            if current_size == expected_size:
                self.completed.emit("skipped")
                return
            if current_size is not None and not self.overwrite:
                self.completed.emit("different")
                return
            if self.cancel_event.is_set():
                self.completed.emit("cancelled")
                return

            if source is None:
                source = self._resolve_source()
                if source.stat().st_size != expected_size:
                    raise IOError(
                        f"RomM download size mismatch for {self.remote_game.name}: "
                        f"expected {expected_size} bytes, got {source.stat().st_size}."
                    )

            self.status_changed.emit(
                f"Copying {self.remote_game.name} to the mounted Nintendo 3DS SD card…"
            )
            result, _ = backend.upload(
                source,
                self.destination,
                overwrite=self.overwrite,
                cancel_event=self.cancel_event,
                progress=self.progress.emit,
            )
            self.completed.emit(result)
        except InterruptedError:
            self.completed.emit("cancelled")
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if self._temporary_path is not None:
                try:
                    self._temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass


class ThreeDSFilesystemDeployDialog(QDialog):
    """Focused transport choice after a 3DS game and filesystem target are known."""

    def __init__(self, config: dict, game: RomMRemoteGame, target_key: str, parent=None):
        super().__init__(parent)
        self.config = config
        self.game = game
        self.target_key = target_key
        self.library_source = get_library_source(config)
        self.storage_root = configured_3ds_storage_root(config)
        self.worker: QThread | None = None
        self._last_result: str | None = None
        self._active_transport = ""

        saved = config.get("devices", {}).get("3ds", {})
        self._ftp_host = str(saved.get("host", "")).strip()
        try:
            self._ftp_port = int(saved.get("port", 5000))
        except (TypeError, ValueError):
            self._ftp_port = 5000

        self.destination = default_destination(target_key, game.platform_slug, game.filename)

        self.setWindowTitle("Deploy to Nintendo 3DS")
        self.resize(720, 500)
        self.setMinimumSize(620, 450)

        header = SectionHeader(
            "Deploy to Nintendo 3DS",
            "The runtime and destination are already selected. Choose how the file should reach the console storage.",
        )

        summary = SurfaceCard()
        summary.content.addWidget(self._card_title(game.name))
        summary.content.addWidget(
            self._secondary(
                f"{game.platform} · {game.size:,} bytes\nDestination: {self.destination}"
            )
        )

        route_card = SurfaceCard()
        route_card.content.addWidget(self._card_title("Transfer method"))
        route_card.content.addWidget(
            self._secondary(
                "Mounted SD is the direct/offline route when the 3DS SD or microSD card is in a computer/card reader. ftpd is the wireless live-console route. RommHeld does not label the 3DS card-reader route as USB because the console does not expose standard USB mass storage."
            )
        )
        self.transport_combo = QComboBox()
        if self.storage_root is not None:
            self.transport_combo.addItem("Mounted SD card · Direct / offline", "sd")
        if self._ftp_host:
            self.transport_combo.addItem("ftpd · Wireless / live console", "ftp")
        if not self.transport_combo.count():
            self.transport_combo.addItem("No filesystem route configured", "")
        self.transport_combo.currentIndexChanged.connect(self._transport_changed)
        route_card.content.addWidget(self.transport_combo)

        self.route_status = StatusPill("Route", "Not ready")
        self.route_detail = QLabel()
        self.route_detail.setWordWrap(True)
        self.route_detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow(self.route_status, self.route_detail)
        route_card.content.addLayout(form)

        activity = SurfaceCard()
        activity.content.addWidget(self._card_title("Transfer"))
        self.status = QLabel("Choose an available transfer method.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color:{DARK.text_secondary};")
        activity.content.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        activity.content.addWidget(self.progress)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_button = QPushButton("Cancel transfer")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_transfer)
        self.deploy_button = AccentButton("Deploy", NINTENDO_RED)
        self.deploy_button.clicked.connect(self.start_transfer)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.deploy_button)
        activity.content.addLayout(actions)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        close_row.addWidget(close)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(header)
        layout.addWidget(summary)
        layout.addWidget(route_card)
        layout.addWidget(activity)
        layout.addStretch(1)
        layout.addLayout(close_row)

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

    def _selected_transport(self) -> str:
        return str(self.transport_combo.currentData() or "")

    def _transport_changed(self, _index: int | None = None) -> None:
        transport = self._selected_transport()
        if transport == "sd" and self.storage_root is not None:
            self.route_status.set_value("Mounted SD")
            self.route_detail.setText(str(self.storage_root))
            self.status.setText(
                "Ready for a safe direct copy. Keep the card mounted until the transfer completes, then eject it cleanly before returning it to the 3DS."
            )
            self.deploy_button.setEnabled(True)
        elif transport == "ftp" and self._ftp_host:
            self.route_status.set_value("ftpd")
            self.route_detail.setText(f"ftp://{self._ftp_host}:{self._ftp_port}")
            self.status.setText(
                "Ready to connect. Open ftpd on the Nintendo 3DS and leave it running during the transfer."
            )
            self.deploy_button.setEnabled(True)
        else:
            self.route_status.set_value("Setup required")
            self.route_detail.setText(
                "Configure a mounted 3DS SD card or ftpd from the Device page first."
            )
            self.status.setText("No 3DS filesystem transfer route is currently available.")
            self.deploy_button.setEnabled(False)

    def _ftp_settings(self) -> ThreeDSFtpSettings:
        saved = self.config.get("devices", {}).get("3ds", {})
        if not self._ftp_host:
            raise ValueError("Nintendo 3DS ftpd is not configured.")
        if not 1 <= self._ftp_port <= 65535:
            raise ValueError("Nintendo 3DS FTP port must be between 1 and 65535.")
        return ThreeDSFtpSettings(
            host=self._ftp_host,
            port=self._ftp_port,
            username=str(saved.get("username", "anonymous")).strip() or "anonymous",
            password=str(saved.get("password", "")),
            remote_root=str(saved.get("remote_root", "/")).strip() or "/",
        )

    def start_transfer(self, _checked: bool = False, *, overwrite: bool = False) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        transport = self._selected_transport()
        if transport not in {"sd", "ftp"}:
            return

        self._last_result = None
        self._active_transport = transport
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.transport_combo.setEnabled(False)
        self.deploy_button.setEnabled(False)
        self.cancel_button.setVisible(True)
        self.cancel_button.setEnabled(True)
        self.status.setText(
            f"Preparing verified replacement for {self.game.name}…"
            if overwrite
            else f"Checking destination for {self.game.name}…"
        )

        if transport == "sd":
            root = configured_3ds_storage_root(self.config)
            if root is None:
                self._reset_after_failure(
                    "The configured Nintendo 3DS SD card is no longer mounted or no longer validates as a 3DS root."
                )
                return
            worker: QThread = ThreeDSMountedTransferWorker(
                root,
                self.destination,
                remote_game=self.game,
                romm_url=self.library_source.romm_url,
                romm_token=self.library_source.api_token,
                overwrite=overwrite,
            )
        else:
            try:
                settings = self._ftp_settings()
            except ValueError as exc:
                self._reset_after_failure(str(exc))
                return
            worker = ThreeDSTransferWorker(
                settings,
                None,
                self.destination,
                remote_game=self.game,
                romm_url=self.library_source.romm_url,
                romm_token=self.library_source.api_token,
                overwrite=overwrite,
            )

        self.worker = worker
        worker.status_changed.connect(self.status.setText)
        worker.progress.connect(self._progress)
        worker.completed.connect(self._completed)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._finished)
        worker.start()

    def _progress(self, done: int) -> None:
        total = int(self.game.size)
        if total > 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(min(100, int(done * 100 / total)))
        else:
            self.progress.setRange(0, 0)

    def _completed(self, result: str) -> None:
        self._last_result = result
        messages = {
            "copied": "Transfer complete. The final destination was size verified.",
            "resumed": "The matching RommHeld FTP stage resumed, verified, and moved into place.",
            "skipped": "The destination already contains the same-size file. No download or replacement was needed.",
            "different": "A different-size file already exists. Nothing was changed.",
            "cancelled": "Transfer cancelled. The existing destination was preserved.",
        }
        self.status.setText(messages.get(result, result))

    def _failed(self, message: str) -> None:
        self._last_result = None
        if self._active_transport == "ftp":
            prefix = (
                "ftpd transfer failed. Confirm ftpd is open on the 3DS and that the saved IP address and port still match. "
            )
        else:
            prefix = (
                "Mounted-SD transfer failed. Confirm the card is still mounted and writable. "
            )
        self.status.setText(prefix + message)

    def _finished(self) -> None:
        result = self._last_result
        self.worker = None
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        self.cancel_button.setVisible(False)
        self.transport_combo.setEnabled(True)

        if result == "different":
            answer = QMessageBox.question(
                self,
                "Replace existing 3DS file?",
                "The destination contains a different-size file. Replace it? RommHeld stages the new file and keeps the existing destination until the replacement has completed safely.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.start_transfer(overwrite=True)
                return
        self._transport_changed()

    def _reset_after_failure(self, message: str) -> None:
        self.worker = None
        self.progress.setVisible(False)
        self.cancel_button.setVisible(False)
        self.transport_combo.setEnabled(True)
        self.status.setText(message)
        self._transport_changed()

    def cancel_transfer(self) -> None:
        worker = self.worker
        if worker is not None and worker.isRunning() and hasattr(worker, "cancel"):
            worker.cancel()
            self.cancel_button.setEnabled(False)
            self.status.setText("Cancelling transfer…")

    def closeEvent(self, event: QCloseEvent) -> None:
        worker = self.worker
        if worker is not None and worker.isRunning():
            if hasattr(worker, "cancel"):
                worker.cancel()
            self.cancel_button.setEnabled(False)
            self.status.setText("Cancelling the active transfer before closing…")
            event.ignore()
            return
        super().closeEvent(event)


__all__ = ["ThreeDSFilesystemDeployDialog", "ThreeDSMountedTransferWorker"]
