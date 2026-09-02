from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from urllib import error, request

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QDialog,
)

from .config import save_config
from .gba_vc import build_native_gba_cia, native_title_id_for_romm_id, read_asset
from .romm_remote import RomMRemoteGame, download_rom
from .three_ds_ftp import ThreeDSFtpBackend, ThreeDSFtpSettings
from .three_ds_targets import default_destination


class GbaCiaDeployWorker(QThread):
    progress = Signal(int)
    status_changed = Signal(str)
    completed = Signal(str, str)
    failed = Signal(str)

    def __init__(self, config: dict, game: RomMRemoteGame, target_key: str, boot_logo: Path, destination: str):
        super().__init__()
        self.config = config
        self.game = game
        self.target_key = target_key
        self.boot_logo = boot_logo
        self.destination = destination
        self.cancel_event = threading.Event()
        self.backend: ThreeDSFtpBackend | None = None
        self.temp_rom: Path | None = None

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            source = self.config.get("library_source", {})
            url = str(source.get("romm_url", "")).strip()
            token = str(source.get("api_token", "")).strip()
            if not url or not token:
                raise ValueError("RomM Server is not configured.")

            handle = tempfile.NamedTemporaryFile(prefix="rommheld-gba-", suffix=".gba", delete=False)
            handle.close()
            self.temp_rom = Path(handle.name)
            self.status_changed.emit(f"Downloading {self.game.name} from RomM…")
            download_rom(url, token, self.game, self.temp_rom)
            if self.cancel_event.is_set():
                return

            self.status_changed.emit("Packaging GBA title…")
            rom_data = self.temp_rom.read_bytes()
            artwork_url = self.game.cover_url
            artwork = self._download_artwork(artwork_url, token) if artwork_url else None
            if not artwork:
                raise ValueError("No usable RomM artwork is available for this title.")

            cia = build_native_gba_cia(
                rom_data,
                artwork,
                boot_logo=read_asset(self.boot_logo),
                title_id=native_title_id_for_romm_id(self.game.rom_id),
                title_name=self.game.name,
            )
            if self.cancel_event.is_set():
                return

            handle = tempfile.NamedTemporaryFile(prefix="rommheld-gba-", suffix=".cia", delete=False)
            handle.write(cia)
            handle.close()
            cia_path = Path(handle.name)
            try:
                self.status_changed.emit("Uploading CIA to the 3DS…")
                saved = self.config.get("devices", {}).get("3ds", {})
                settings = ThreeDSFtpSettings(
                    host=str(saved.get("host", "")).strip(),
                    port=int(saved.get("port", 5000)),
                    username=str(saved.get("username", "anonymous")),
                    password=str(saved.get("password", "")),
                    remote_root=str(saved.get("remote_root", "/")),
                )
                self.backend = ThreeDSFtpBackend(settings)
                self.backend.connect()
                result, _ = self.backend.upload(
                    cia_path,
                    self.destination,
                    cancel_event=self.cancel_event,
                    progress=self._progress,
                )
                self.completed.emit(result, self.destination)
            finally:
                cia_path.unlink(missing_ok=True)
        except InterruptedError:
            self.status_changed.emit("Deployment cancelled.")
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if self.backend is not None:
                self.backend.close()
            if self.temp_rom is not None:
                self.temp_rom.unlink(missing_ok=True)

    def _progress(self, done: int) -> None:
        try:
            self.progress.emit(done)
        except RuntimeError:
            pass

    @staticmethod
    def _download_artwork(url: str | None, token: str) -> bytes | None:
        if not url:
            return None
        headers = {
            "Authorization": f"Bearer {token.strip()}",
            "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*",
            "User-Agent": "RommHeld",
        }
        try:
            with request.urlopen(request.Request(url, headers=headers), timeout=10) as response:
                data = response.read(8 * 1024 * 1024 + 1)
        except (error.HTTPError, error.URLError, TimeoutError):
            return None
        return data if len(data) <= 8 * 1024 * 1024 else None


class GbaVcDeployDialog(QDialog):
    def __init__(self, config: dict, game: RomMRemoteGame, target_key: str, parent=None):
        super().__init__(parent)
        self.config = config
        self.game = game
        self.target_key = target_key
        self.worker: GbaCiaDeployWorker | None = None
        self.setWindowTitle("Deploy GBA to Nintendo 3DS")
        self.resize(760, 520)

        self.title_label = QLabel(game.name)
        self.title_label.setStyleSheet("font-size:18px;font-weight:800;")
        mode = "Native AGB_FIRM" if target_key == "native_gba" else "Virtual Console-style CIA"
        self.mode_label = QLabel(f"Mode: {mode}")
        self.mode_label.setStyleSheet("color:#8d96a4;")

        self.boot_logo_edit = QLineEdit()
        self.boot_logo_edit.setPlaceholderText("Extracted AGB_FIRM boot logo")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.browse_boot_logo)
        boot_row = QHBoxLayout()
        boot_row.addWidget(self.boot_logo_edit, 1)
        boot_row.addWidget(browse)

        self.title_id_edit = QLineEdit(native_title_id_for_romm_id(game.rom_id).hex())
        self.title_id_edit.setReadOnly(True)
        self.title_id_edit.setToolTip("Generated deterministically inside Nintendo's GBA Virtual Console title-ID range.")

        self.destination_edit = QLineEdit(default_destination("vc_cia", "gba", game.filename))
        self.destination_edit.setReadOnly(True)

        self.ftp_status = QLabel("3DS FTP settings are taken from the configured 3DS device.")
        self.status = QLabel("Select your locally extracted boot logo to continue.")
        self.status.setWordWrap(True)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.deploy = QPushButton("Package and Deploy")
        self.cancel = QPushButton("Cancel")
        self.cancel.setEnabled(False)
        self.deploy.clicked.connect(self.start)
        self.cancel.clicked.connect(self.cancel_deploy)

        actions = QHBoxLayout()
        actions.addWidget(self.deploy)
        actions.addWidget(self.cancel)
        actions.addStretch()

        form = QFormLayout()
        form.addRow("Game:", self.title_label)
        form.addRow("Deployment:", self.mode_label)
        form.addRow("AGB_FIRM boot logo:", boot_row)
        form.addRow("Title ID:", self.title_id_edit)
        form.addRow("Remote CIA:", self.destination_edit)
        form.addRow("FTP:", self.ftp_status)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addLayout(actions)

    def browse_boot_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose extracted AGB_FIRM boot logo")
        if path:
            self.boot_logo_edit.setText(path)
            self.status.setText("Boot logo selected. Ready to package.")

    def start(self) -> None:
        boot_logo = Path(self.boot_logo_edit.text()).expanduser()
        if not boot_logo.is_file():
            QMessageBox.warning(
                self,
                "Boot logo required",
                "Choose an extracted AGB_FIRM boot logo. RomM-held Nintendo assets are not downloaded automatically.",
            )
            return
        saved = self.config.get("devices", {}).get("3ds", {})
        if not str(saved.get("host", "")).strip():
            QMessageBox.warning(self, "3DS FTP not configured", "Configure the Nintendo 3DS FTP host first.")
            return

        self.progress.setValue(0)
        self.status.setText("Preparing deployment…")
        self.deploy.setEnabled(False)
        self.cancel.setEnabled(True)
        self.worker = GbaCiaDeployWorker(
            self.config,
            self.game,
            self.target_key,
            boot_logo,
            self.destination_edit.text(),
        )
        self.worker.progress.connect(self._progress)
        self.worker.status_changed.connect(self.status.setText)
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _progress(self, done: int) -> None:
        # CIA size is unknown until packaging completes; upload progress is byte based.
        self.progress.setValue(min(99, max(0, done // 1024 // 1024)))

    def _completed(self, result: str, destination: str) -> None:
        messages = {
            "copied": f"CIA deployed and verified at {destination}.",
            "resumed": f"CIA resumed and verified at {destination}.",
            "skipped": f"CIA already exists at {destination} with the same size.",
            "different": f"A different-size CIA exists at {destination}; nothing was overwritten.",
        }
        self.progress.setValue(100)
        self.status.setText(messages.get(result, result))
        if result == "different":
            QMessageBox.warning(self, "Existing CIA protected", self.status.text())

    def _failed(self, message: str) -> None:
        self.status.setText(f"Deployment failed: {message}")

    def _finished(self) -> None:
        self.worker = None
        self.deploy.setEnabled(True)
        self.cancel.setEnabled(False)

    def cancel_deploy(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.status.setText("Cancelling…")

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1500)
        super().closeEvent(event)
