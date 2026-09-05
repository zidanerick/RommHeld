from __future__ import annotations

import tempfile
import threading
import webbrowser
from pathlib import Path

from PySide6.QtCore import QThread, Signal
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
)

from .classic_vc import build_classic_vc_cia
from .classic_vc_assets import configured_classic_runtime, extract_and_cache_classic_runtime
from .config import save_config
from .design_tokens import DARK, brand_for_platform
from .fbi_remote_install import FBIUrlServer
from .firewall import FirewallError, FirewallRule, allow_temporary, remove_temporary
from .hshop_catalog import HShopVcRelease, find_official_vc_release
from .romm_remote import RomMRemoteGame, download_artwork, download_rom
from .three_ds_ftp import ThreeDSFtpBackend, ThreeDSFtpSettings
from .three_ds_storage import ThreeDSMountedStorageBackend, configured_3ds_storage_root
from .three_ds_targets import default_destination
from .ui_components import AccentButton, SurfaceCard
from .vc_donors import configured_boot9_path, configured_donor_path
from .vc_runtime_profiles import guidance_for_family, runtime_guidance_summary
from .vc_title_id_registry import displayed_title_id, persist_registered_title_id


_FAMILY_LABELS = {
    "gb": "Game Boy",
    "gbc": "Game Boy Color",
    "nes": "NES",
    "gamegear": "Game Gear",
    "snes": "Super Nintendo",
}
_FAMILY_SUFFIXES = {
    "gb": ".gb",
    "gbc": ".gbc",
    "nes": ".nes",
    "gamegear": ".gg",
    "snes": ".sfc",
}


class ClassicHShopLookupWorker(QThread):
    completed = Signal(object)

    def __init__(self, title: str, platform_slug: str):
        super().__init__()
        self.title = title
        self.platform_slug = platform_slug

    def run(self) -> None:
        self.completed.emit(find_official_vc_release(self.title, self.platform_slug))


class ClassicVcDeployWorker(QThread):
    progress = Signal(int)
    status_changed = Signal(str)
    completed = Signal(str, str)
    failed = Signal(str)

    def __init__(
        self,
        config: dict,
        game: RomMRemoteGame,
        family: str,
        destination: str,
        install_method: str,
        three_ds_ip: str,
        display_title: str,
        publisher: str,
    ):
        super().__init__()
        self.config = config
        self.game = game
        self.family = family
        self.destination = destination
        self.install_method = install_method
        self.three_ds_ip = three_ds_ip.strip()
        self.display_title = display_title.strip() or game.name
        self.publisher = publisher.strip()
        self.cancel_event = threading.Event()
        self.backend: ThreeDSFtpBackend | None = None
        self.fbi_server: FBIUrlServer | None = None
        self.firewall_rule: FirewallRule | None = None
        self.temp_rom: Path | None = None
        self._transfer_total = 0

    def cancel(self) -> None:
        self.cancel_event.set()

    def _check_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise InterruptedError

    def _progress(self, done: int) -> None:
        total = self._transfer_total
        percent = int(done * 100 / total) if total else 0
        try:
            self.progress.emit(max(0, min(99, percent)))
        except RuntimeError:
            pass

    def run(self) -> None:
        try:
            platform = (self.game.platform_slug or self.game.platform).strip().lower()
            if platform != self.family or self.family not in _FAMILY_LABELS:
                raise ValueError(f"Classic Nintendo VC packaging is not available for {platform or 'this platform'}.")

            runtime_paths = configured_classic_runtime(self.config, self.family)
            if runtime_paths is None:
                raise ValueError(f"Prepare the {_FAMILY_LABELS[self.family]} Virtual Console runtime first.")

            source = self.config.get("library_source", {})
            url = str(source.get("romm_url", "")).strip()
            token = str(source.get("api_token", "")).strip()
            if not url or not token:
                raise ValueError("RomM Server is not configured.")

            suffix = _FAMILY_SUFFIXES[self.family]
            handle = tempfile.NamedTemporaryFile(prefix=f"rommheld-{self.family}-", suffix=suffix, delete=False)
            handle.close()
            self.temp_rom = Path(handle.name)
            self.status_changed.emit(f"Downloading {self.game.name} from RomM…")
            download_rom(
                url,
                token,
                self.game,
                self.temp_rom,
                cancel_event=self.cancel_event,
            )
            self._check_cancelled()

            self.status_changed.emit("Fetching RomM artwork…")
            artwork = download_artwork(url, token, self.game.cover_url) if self.game.cover_url else None
            if not artwork:
                raise ValueError("No usable RomM artwork is available for this title.")
            self._check_cancelled()

            self.status_changed.emit("Allocating a stable RommHeld Title ID…")
            self.config, title_id = persist_registered_title_id(self.family, self.game.rom_id)
            self._check_cancelled()

            self.status_changed.emit(
                f"Packaging {_FAMILY_LABELS[self.family]} Nintendo Virtual Console CIA with retail donor presentation…"
            )
            cia = build_classic_vc_cia(
                self.temp_rom.read_bytes(),
                artwork,
                runtime_paths.load(),
                romm_id=self.game.rom_id,
                title_name=self.display_title,
                long_title=self.display_title,
                publisher=self.publisher,
                release_year=self.game.release_year,
                title_id_override=title_id,
            )
            self._check_cancelled()

            cia_handle = tempfile.NamedTemporaryFile(prefix=f"rommheld-{self.family}-", suffix=".cia", delete=False)
            cia_handle.write(cia)
            cia_handle.close()
            cia_path = Path(cia_handle.name)
            try:
                self._transfer_total = cia_path.stat().st_size
                if self.install_method == "fbi":
                    if not self.three_ds_ip:
                        raise ValueError("Enter the 3DS IP address shown by FBI Remote Install.")
                    self.status_changed.emit("Preparing FBI Remote Install…")
                    self.fbi_server = FBIUrlServer(cia_path)
                    server_ip = self.fbi_server.local_address(peer_host=self.three_ds_ip)
                    self.firewall_rule = allow_temporary(
                        self.three_ds_ip,
                        self.fbi_server.port,
                        destination_ip=server_ip,
                    )
                    self._check_cancelled()
                    self.fbi_server.start()
                    served_url = self.fbi_server.send_to_fbi(self.three_ds_ip, host=server_ip)
                    self.status_changed.emit(
                        f"FBI received {served_url}. Confirm 'Install from the received URL(s)?' on the 3DS."
                    )
                    self.fbi_server.wait_for_download(cancel_event=self.cancel_event)
                    self._check_cancelled()
                    self.progress.emit(100)
                    self.completed.emit("fbi", self.destination)
                    return

                if self.install_method == "sd":
                    root = configured_3ds_storage_root(self.config)
                    if root is None:
                        raise ValueError(
                            "No validated Nintendo 3DS SD card is mounted. Configure Mounted SD on the Device page first."
                        )
                    self.status_changed.emit("Copying CIA to the mounted Nintendo 3DS SD card…")
                    storage = ThreeDSMountedStorageBackend(root)
                    result, _ = storage.upload(
                        cia_path,
                        self.destination,
                        cancel_event=self.cancel_event,
                        progress=self._progress,
                    )
                    self._check_cancelled()
                    self.progress.emit(100)
                    self.completed.emit(result, self.destination)
                    return

                self.status_changed.emit("Connecting to Nintendo 3DS FTP…")
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
                self._check_cancelled()
                self.status_changed.emit("Uploading CIA to the Nintendo 3DS…")
                result, _ = self.backend.upload(
                    cia_path,
                    self.destination,
                    cancel_event=self.cancel_event,
                    progress=self._progress,
                )
                self._check_cancelled()
                self.progress.emit(100)
                self.completed.emit(result, self.destination)
            finally:
                cia_path.unlink(missing_ok=True)
        except InterruptedError:
            self.status_changed.emit("Deployment cancelled.")
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if self.fbi_server is not None:
                self.fbi_server.close()
            if self.firewall_rule is not None:
                try:
                    remove_temporary(self.firewall_rule)
                except FirewallError as exc:
                    self.status_changed.emit(f"Warning: could not clean up firewall state: {exc}")
            if self.backend is not None:
                self.backend.close()
            if self.temp_rom is not None:
                self.temp_rom.unlink(missing_ok=True)


class ClassicVcDeployDialog(QDialog):
    def __init__(self, config: dict, game: RomMRemoteGame, parent=None):
        super().__init__(parent)
        self.config = config
        self.game = game
        self.family = (game.platform_slug or game.platform).strip().lower()
        if self.family not in _FAMILY_LABELS:
            raise ValueError(f"Unsupported classic VC family: {self.family}")
        self.worker: ClassicVcDeployWorker | None = None
        self.hshop_worker: ClassicHShopLookupWorker | None = None
        self.official_release: HShopVcRelease | None = None
        family_label = _FAMILY_LABELS[self.family]
        accent = brand_for_platform("3ds").accent

        self.setWindowTitle(f"Deploy {family_label} to Nintendo 3DS")
        self.resize(790, 720)

        header = QVBoxLayout()
        title = QLabel(game.name)
        title.setStyleSheet(f"color:{DARK.text_primary};font-size:22px;font-weight:700;")
        mode = QLabel(f"{family_label} Virtual Console CIA")
        mode.setStyleSheet(f"color:{accent};font-size:11px;font-weight:600;")
        header.addWidget(title)
        header.addWidget(mode)

        official = SurfaceCard()
        official.content.addWidget(QLabel("Official Nintendo Virtual Console"))
        self.official_status = QLabel(f"Checking hShop catalogue for an official {family_label} Virtual Console release…")
        self.official_status.setWordWrap(True)
        self.official_status.setStyleSheet(f"color:{DARK.text_secondary};font-size:10px;")
        official.content.addWidget(self.official_status)
        self.open_official_button = QPushButton("Open official release")
        self.open_official_button.setEnabled(False)
        self.open_official_button.clicked.connect(self._open_official_release)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.open_official_button)
        official.content.addLayout(row)

        runtime_card = SurfaceCard()
        runtime_card.content.addWidget(QLabel(f"{family_label} Virtual Console runtime"))
        self.runtime_guidance = QLabel()
        self.runtime_guidance.setWordWrap(True)
        self.runtime_guidance.setStyleSheet(f"color:{DARK.text_secondary};font-size:10px;")
        runtime_card.content.addWidget(self.runtime_guidance)
        self._refresh_runtime_guidance()
        runtime = configured_classic_runtime(config, self.family)
        donor = configured_donor_path(config, self.family)
        boot9 = configured_boot9_path(config)
        self.donor_edit = QLineEdit(str(donor) if donor else "")
        self.boot9_edit = QLineEdit(str(boot9) if boot9 else "")
        self.runtime_status = QLabel()
        self.runtime_status.setWordWrap(True)
        self.runtime_status.setStyleSheet(f"color:{DARK.text_secondary};font-size:10px;")
        if runtime is not None:
            self.runtime_status.setText(
                "Ready — the donor emulator runtime, animated banner and official HOME Menu icon presentation are cached locally. "
                "The original donor CIA and boot9 dump are not required for normal deployments."
            )
            runtime_card.content.addWidget(self.runtime_status)
        else:
            note = QLabel(
                f"One-time setup: choose a genuine {family_label} Virtual Console donor CIA and your own boot9 dump. "
                "RommHeld caches the emulator runtime and retail presentation while removing the donor game payload from the reusable runtime."
            )
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{DARK.text_secondary};font-size:10px;")
            runtime_card.content.addWidget(note)
            donor_button = QPushButton("Browse…")
            donor_button.clicked.connect(self._choose_donor)
            donor_row = QHBoxLayout()
            donor_row.addWidget(self.donor_edit, 1)
            donor_row.addWidget(donor_button)
            boot_button = QPushButton("Browse…")
            boot_button.clicked.connect(self._choose_boot9)
            boot_row = QHBoxLayout()
            boot_row.addWidget(self.boot9_edit, 1)
            boot_row.addWidget(boot_button)
            form = QFormLayout()
            form.addRow(f"{family_label} VC donor", donor_row)
            form.addRow("boot9 dump", boot_row)
            runtime_card.content.addLayout(form)
            runtime_card.content.addWidget(self.runtime_status)
            prepare = QPushButton("Prepare VC runtime")
            prepare.clicked.connect(self._prepare_runtime)
            prepare_row = QHBoxLayout()
            prepare_row.addStretch()
            prepare_row.addWidget(prepare)
            runtime_card.content.addLayout(prepare_row)
            self.runtime_status.setText("Runtime/presentation cache is not prepared yet.")

        configuration = SurfaceCard()
        configuration.content.addWidget(QLabel("Delivery"))
        self.display_title_edit = QLineEdit(game.name)
        self.display_title_edit.setReadOnly(True)
        self.publisher_edit = QLineEdit(game.publisher)
        self.publisher_edit.setReadOnly(True)
        self.publisher_edit.setPlaceholderText("Not available in RomM metadata")
        self.title_id_edit = QLineEdit(displayed_title_id(config, self.family, game.rom_id).hex())
        self.title_id_edit.setReadOnly(True)
        self.title_id_edit.setToolTip(
            "Current RommHeld assignment, or the preferred candidate if this title has not been deployed yet."
        )
        self.destination_edit = QLineEdit(default_destination("vc_cia", self.family, game.filename))
        self.destination_edit.setReadOnly(True)
        saved = config.get("devices", {}).get("3ds", {})
        self.three_ds_ip_edit = QLineEdit(str(saved.get("ip", "")))
        self.three_ds_ip_edit.setPlaceholderText("3DS IP shown by FBI")
        self.three_ds_ip_edit.editingFinished.connect(self._save_3ds_ip)
        self.install_method = QComboBox()
        self.install_method.addItem("FBI Remote Install · Install directly", "fbi")
        self.install_method.addItem("Mounted SD card · Copy CIA", "sd")
        self.install_method.addItem("ftpd · Copy CIA", "ftp")
        self.install_method.currentIndexChanged.connect(self._install_method_changed)
        form = QFormLayout()
        form.addRow("Delivery method", self.install_method)
        form.addRow("3DS IP", self.three_ds_ip_edit)
        form.addRow("Display title", self.display_title_edit)
        form.addRow("Publisher", self.publisher_edit)
        form.addRow("Title ID", self.title_id_edit)
        form.addRow("Destination", self.destination_edit)
        configuration.content.addLayout(form)
        self.delivery_hint = QLabel()
        self.delivery_hint.setWordWrap(True)
        self.delivery_hint.setStyleSheet(f"color:{DARK.text_secondary};font-size:10px;")
        configuration.content.addWidget(self.delivery_hint)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.status = QLabel("Ready")
        self.status.setWordWrap(True)
        self.deploy = AccentButton("Build and deploy VC CIA", accent)
        self.deploy.clicked.connect(self._start)
        self.cancel = QPushButton("Cancel")
        self.cancel.clicked.connect(self.reject)
        actions = QHBoxLayout()
        actions.addWidget(self.cancel)
        actions.addStretch()
        actions.addWidget(self.deploy)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(official)
        layout.addWidget(runtime_card)
        layout.addWidget(configuration)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addLayout(actions)

        self._install_method_changed()
        self._start_hshop_lookup()

    def _refresh_runtime_guidance(self) -> None:
        guidance = guidance_for_family(self.family)
        self.runtime_guidance.setText(runtime_guidance_summary(self.config, self.family))
        self.runtime_guidance.setToolTip("\n".join(guidance.details))

    def _choose_donor(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Virtual Console donor", "", "CIA files (*.cia)")
        if path:
            self.donor_edit.setText(path)

    def _choose_boot9(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select boot9 dump", "", "Binary files (*.bin);;All files (*)")
        if path:
            self.boot9_edit.setText(path)

    def _prepare_runtime(self) -> None:
        try:
            updated, _ = extract_and_cache_classic_runtime(
                self.config,
                self.family,
                Path(self.donor_edit.text().strip()),
                Path(self.boot9_edit.text().strip()),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Runtime preparation failed", str(exc))
            self.runtime_status.setText(str(exc))
            return
        self.config = updated
        self._refresh_runtime_guidance()
        self.runtime_status.setText(
            "Ready — reusable VC runtime and retail presentation cached locally. You can build this title now."
        )
        self.deploy.setEnabled(True)

    def _start_hshop_lookup(self) -> None:
        worker = ClassicHShopLookupWorker(self.game.name, self.family)
        worker.completed.connect(self._official_loaded)
        worker.finished.connect(lambda: setattr(self, "hshop_worker", None))
        self.hshop_worker = worker
        worker.start()

    def _official_loaded(self, release: HShopVcRelease | None) -> None:
        self.official_release = release
        if release is None:
            self.official_status.setText("No confident official Nintendo VC match found. Donor-backed injection remains available.")
            return
        self.display_title_edit.setText(release.title or self.game.name)
        details = [release.title, release.platform]
        if release.region:
            details.append(release.region)
        if release.title_id:
            details.append(release.title_id)
        self.official_status.setText(
            "Official release found: " + " • ".join(item for item in details if item) +
            ". Prefer the official release when you already have lawful local access to it; donor-backed injection remains available as a fallback."
        )
        self.open_official_button.setEnabled(True)

    def _open_official_release(self) -> None:
        if self.official_release is not None:
            webbrowser.open(self.official_release.url)

    def _install_method_changed(self) -> None:
        method = str(self.install_method.currentData() or "")
        fbi = method == "fbi"
        self.three_ds_ip_edit.setEnabled(fbi)
        if fbi:
            self.delivery_hint.setText(
                "FBI Remote Install sends the generated CIA directly to FBI for installation."
            )
        elif method == "sd":
            self.delivery_hint.setText(
                "Copies the generated CIA to the validated mounted 3DS SD card. Eject the card cleanly, return it to the console, then install the CIA with FBI."
            )
        else:
            self.delivery_hint.setText(
                "ftpd copies the generated CIA to the configured 3DS destination while the console is running. Install the copied CIA afterward with FBI."
            )

    def _save_3ds_ip(self) -> None:
        value = self.three_ds_ip_edit.text().strip()
        if not value:
            return
        updated = dict(self.config)
        devices = dict(updated.get("devices", {})) if isinstance(updated.get("devices", {}), dict) else {}
        saved = dict(devices.get("3ds", {})) if isinstance(devices.get("3ds", {}), dict) else {}
        saved["ip"] = value
        devices["3ds"] = saved
        updated["devices"] = devices
        self.config = updated
        save_config(updated)

    def _start(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        if configured_classic_runtime(self.config, self.family) is None:
            self.status.setText("Prepare the donor Virtual Console runtime first.")
            return
        method = str(self.install_method.currentData() or "")
        saved = self.config.get("devices", {}).get("3ds", {})
        if method == "ftp" and not str(saved.get("host", "")).strip():
            self.status.setText("Configure the Nintendo 3DS ftpd endpoint on the Device page first.")
            return
        if method == "sd" and configured_3ds_storage_root(self.config) is None:
            self.status.setText("Mount and validate the Nintendo 3DS SD card from the Device page first.")
            return
        if method == "fbi" and not self.three_ds_ip_edit.text().strip():
            self.status.setText("Enter the 3DS IP address shown by FBI Remote Install first.")
            return
        self.deploy.setEnabled(False)
        self.progress.setValue(0)
        self.status.setText("Preparing deployment…")
        worker = ClassicVcDeployWorker(
            self.config,
            self.game,
            self.family,
            self.destination_edit.text().strip(),
            method,
            self.three_ds_ip_edit.text().strip(),
            self.display_title_edit.text().strip(),
            self.publisher_edit.text().strip(),
        )
        worker.progress.connect(self.progress.setValue)
        worker.status_changed.connect(self.status.setText)
        worker.completed.connect(self._completed)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._worker_finished)
        self.worker = worker
        worker.start()

    def _completed(self, result: str, destination: str) -> None:
        if result == "fbi":
            self.status.setText("FBI finished receiving/installing the generated Virtual Console CIA.")
        else:
            self.status.setText(f"CIA copied to {destination}: {result}. Install it later with FBI.")

    def _failed(self, message: str) -> None:
        self.status.setText(message)
        QMessageBox.critical(self, "Virtual Console deployment failed", message)

    def _worker_finished(self) -> None:
        self.worker = None
        self.deploy.setEnabled(True)

    def closeEvent(self, event) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(2000)
            if self.worker.isRunning():
                event.ignore()
                return
        if self.hshop_worker and self.hshop_worker.isRunning():
            self.hshop_worker.requestInterruption()
            self.hshop_worker.wait(2000)
            if self.hshop_worker.isRunning():
                event.ignore()
                return
        event.accept()
