from __future__ import annotations

import tempfile
import threading
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

from .config import save_config
from .design_tokens import DARK, brand_for_platform
from .fbi_remote_install import FBIUrlServer
from .firewall import FirewallError, FirewallRule, allow_temporary, remove_temporary
from .gba_assets import (
    configured_boot_logo,
    configured_donor_banner,
    save_gba_vc_asset_paths,
)
from .gba_vc import build_native_gba_cia, native_title_id_for_romm_id
from .romm_remote import RomMRemoteGame, download_artwork, download_rom
from .three_ds_ftp import ThreeDSFtpBackend, ThreeDSFtpSettings
from .three_ds_targets import default_destination
from .ui_components import AccentButton, SurfaceCard


class GbaCiaDeployWorker(QThread):
    progress = Signal(int)
    status_changed = Signal(str)
    completed = Signal(str, str)
    failed = Signal(str)

    def __init__(
        self,
        config: dict,
        game: RomMRemoteGame,
        target_key: str,
        destination: str,
        install_method: str,
        three_ds_ip: str,
    ):
        super().__init__()
        self.config = config
        self.game = game
        self.target_key = target_key
        self.destination = destination
        self.install_method = install_method
        self.three_ds_ip = three_ds_ip.strip()
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

    def run(self) -> None:
        try:
            platform = (self.game.platform_slug or self.game.platform).strip().lower()
            if platform != "gba":
                raise ValueError(
                    f"{self.target_key} is currently implemented only for GBA titles. "
                    f"{self.game.name} is identified as {platform or 'an unknown platform'}."
                )

            boot_logo_path = configured_boot_logo(self.config)
            if boot_logo_path is None:
                raise ValueError(
                    "A valid extracted AGB_FIRM boot-logo asset is required before building a GBA CIA. "
                    "Choose the boot-logo file in the deployment window."
                )
            donor_banner_path = configured_donor_banner(self.config)
            if self.target_key == "vc_cia" and donor_banner_path is None:
                raise ValueError(
                    "The GBA Virtual Console CIA target requires a real donor GBA VC banner so the title uses the expected Home Menu presentation. "
                    "Choose an extracted donor banner in the deployment window."
                )

            source = self.config.get("library_source", {})
            url = str(source.get("romm_url", "")).strip()
            token = str(source.get("api_token", "")).strip()
            if not url or not token:
                raise ValueError("RomM Server is not configured.")

            handle = tempfile.NamedTemporaryFile(prefix="rommheld-gba-", suffix=".gba", delete=False)
            handle.close()
            self.temp_rom = Path(handle.name)
            self.status_changed.emit(f"Downloading {self.game.name} from RomM…")
            try:
                download_rom(url, token, self.game, self.temp_rom)
            except TimeoutError as exc:
                raise TimeoutError("Timed out downloading the ROM from RomM.") from exc
            self._check_cancelled()

            self.status_changed.emit("Fetching RomM artwork…")
            try:
                artwork = (
                    download_artwork(url, token, self.game.cover_url)
                    if self.game.cover_url
                    else None
                )
            except TimeoutError as exc:
                raise TimeoutError("Timed out downloading artwork from RomM.") from exc
            if not artwork:
                raise ValueError("No usable RomM artwork is available for this title.")
            self._check_cancelled()

            self.status_changed.emit("Packaging GBA CIA for AGB_FIRM…")
            cia = build_native_gba_cia(
                self.temp_rom.read_bytes(),
                artwork,
                boot_logo=boot_logo_path.read_bytes(),
                donor_banner=(
                    donor_banner_path.read_bytes() if donor_banner_path is not None else None
                ),
                title_id=native_title_id_for_romm_id(self.game.rom_id),
                title_name=self.game.name,
            )
            self._check_cancelled()

            handle = tempfile.NamedTemporaryFile(prefix="rommheld-gba-", suffix=".cia", delete=False)
            handle.write(cia)
            handle.close()
            cia_path = Path(handle.name)
            try:
                self._transfer_total = cia_path.stat().st_size
                if self.install_method == "fbi":
                    self.status_changed.emit("Preparing FBI Remote Install…")
                    if not self.three_ds_ip:
                        raise ValueError(
                            "Enter the 3DS IP address shown by FBI Remote Install."
                        )

                    self.fbi_server = FBIUrlServer(cia_path)
                    server_ip = self.fbi_server.local_address(peer_host=self.three_ds_ip)
                    self.status_changed.emit("Requesting temporary firewall access…")
                    self.firewall_rule = allow_temporary(
                        self.three_ds_ip,
                        self.fbi_server.port,
                        destination_ip=server_ip,
                    )
                    self._check_cancelled()
                    if self.firewall_rule is not None:
                        self.status_changed.emit(
                            f"Firewall access granted for {self.three_ds_ip} → {server_ip}:{self.fbi_server.port}."
                        )
                    else:
                        self.status_changed.emit(
                            "No supported active firewall detected; continuing…"
                        )

                    self.fbi_server.start()
                    served_url = self.fbi_server.send_to_fbi(
                        self.three_ds_ip, host=server_ip
                    )
                    self.status_changed.emit(
                        f"FBI accepted the request. Serving the CIA from {served_url}. Confirm installation on the 3DS…"
                    )
                    self.fbi_server.wait_for_download(cancel_event=self.cancel_event)
                    self._check_cancelled()
                    self.progress.emit(100)
                    self.completed.emit("fbi", self.destination)
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
                try:
                    self.backend.connect()
                except TimeoutError as exc:
                    raise TimeoutError(
                        "Timed out connecting to the 3DS FTP server."
                    ) from exc
                self._check_cancelled()

                self.status_changed.emit("Uploading CIA to the Nintendo 3DS…")
                try:
                    result, _ = self.backend.upload(
                        cia_path,
                        self.destination,
                        cancel_event=self.cancel_event,
                        progress=self._progress,
                    )
                except TimeoutError as exc:
                    raise TimeoutError(
                        "Timed out uploading the CIA to the 3DS FTP server."
                    ) from exc
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
                    self.status_changed.emit(
                        f"Warning: could not remove temporary firewall rule: {exc}"
                    )
            if self.backend is not None:
                self.backend.close()
            if self.temp_rom is not None:
                self.temp_rom.unlink(missing_ok=True)

    def _progress(self, done: int) -> None:
        total = self._transfer_total
        percent = int(done * 100 / total) if total else 0
        try:
            self.progress.emit(max(0, min(99, percent)))
        except RuntimeError:
            pass


class GbaVcDeployDialog(QDialog):
    def __init__(
        self,
        config: dict,
        game: RomMRemoteGame,
        target_key: str,
        parent=None,
    ):
        super().__init__(parent)
        self.config = config
        self.game = game
        self.target_key = target_key
        self.worker: GbaCiaDeployWorker | None = None
        self.setWindowTitle("Deploy GBA to Nintendo 3DS")
        self.resize(780, 680)
        self.setMinimumWidth(700)

        accent = brand_for_platform("3ds").accent

        header = QVBoxLayout()
        header.setSpacing(3)
        self.title_label = QLabel(game.name)
        self.title_label.setStyleSheet(
            f"color:{DARK.text_primary};font-size:22px;font-weight:700;"
        )
        mode = (
            "Native GBA (AGB_FIRM)"
            if target_key == "native_gba"
            else "GBA Virtual Console CIA"
        )
        self.mode_label = QLabel(mode)
        self.mode_label.setStyleSheet(
            f"color:{accent};font-size:11px;font-weight:600;"
        )
        header.addWidget(self.title_label)
        header.addWidget(self.mode_label)

        assets = SurfaceCard()
        assets_title = QLabel("Required GBA VC assets")
        assets_title.setStyleSheet("font-size:14px;font-weight:700;")
        assets.content.addWidget(assets_title)
        asset_note = QLabel(
            "Native AGB_FIRM titles need a real boot-logo region extracted from a GBA Virtual Console title you own. "
            "The Virtual Console presentation additionally uses an extracted donor banner for the authentic rotating box scene."
        )
        asset_note.setWordWrap(True)
        asset_note.setStyleSheet(f"color:{DARK.text_secondary};font-size:10px;")
        assets.content.addWidget(asset_note)

        boot_logo = configured_boot_logo(config)
        self.boot_logo_edit = QLineEdit(str(boot_logo) if boot_logo else "")
        self.boot_logo_edit.setPlaceholderText("Extracted AGB_FIRM boot logo (.bin)")
        boot_browse = QPushButton("Browse…")
        boot_browse.clicked.connect(self._choose_boot_logo)
        boot_row = QHBoxLayout()
        boot_row.addWidget(self.boot_logo_edit, 1)
        boot_row.addWidget(boot_browse)

        donor_banner = configured_donor_banner(config)
        self.donor_banner_edit = QLineEdit(
            str(donor_banner) if donor_banner else ""
        )
        self.donor_banner_edit.setPlaceholderText("Extracted GBA VC ExeFS banner")
        donor_browse = QPushButton("Browse…")
        donor_browse.clicked.connect(self._choose_donor_banner)
        donor_row = QHBoxLayout()
        donor_row.addWidget(self.donor_banner_edit, 1)
        donor_row.addWidget(donor_browse)

        asset_form = QFormLayout()
        asset_form.setContentsMargins(0, 0, 0, 0)
        asset_form.addRow("AGB_FIRM boot logo", boot_row)
        asset_form.addRow("VC donor banner", donor_row)
        assets.content.addLayout(asset_form)
        self.donor_banner_edit.setEnabled(target_key == "vc_cia")
        donor_browse.setEnabled(target_key == "vc_cia")

        configuration = SurfaceCard()
        configuration_title = QLabel("Installation")
        configuration_title.setStyleSheet("font-size:14px;font-weight:700;")
        configuration.content.addWidget(configuration_title)

        self.title_id_edit = QLineEdit(native_title_id_for_romm_id(game.rom_id).hex())
        self.title_id_edit.setReadOnly(True)
        self.title_id_edit.setToolTip(
            "Generated deterministically inside the GBA Virtual Console title-ID range."
        )

        self.destination_edit = QLineEdit(
            default_destination("vc_cia", "gba", game.filename)
        )
        self.destination_edit.setReadOnly(True)

        saved = config.get("devices", {}).get("3ds", {})
        self.three_ds_ip_edit = QLineEdit(str(saved.get("ip", "")))
        self.three_ds_ip_edit.setPlaceholderText("3DS IP shown by FBI")
        self.three_ds_ip_edit.setToolTip(
            "The IP shown by FBI > Remote Install > Receive URLs over the network."
        )
        self.three_ds_ip_edit.editingFinished.connect(self._save_3ds_ip)

        self.install_method_combo = QComboBox()
        self.install_method_combo.addItem("FBI Remote Install", "fbi")
        self.install_method_combo.addItem("3DS FTP (copy CIA)", "ftp")
        self.install_method_combo.currentIndexChanged.connect(
            self._install_method_changed
        )

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(9)
        form.addRow("Install with", self.install_method_combo)
        form.addRow("3DS IP", self.three_ds_ip_edit)
        form.addRow("Title ID", self.title_id_edit)
        form.addRow("CIA destination", self.destination_edit)
        configuration.content.addLayout(form)

        self.install_hint = QLabel()
        self.install_hint.setWordWrap(True)
        self.install_hint.setStyleSheet(
            f"color:{DARK.text_secondary};font-size:10px;"
        )
        configuration.content.addWidget(self.install_hint)

        self.ftp_status = QLabel("FTP uses the saved Nintendo 3DS device settings.")
        self.ftp_status.setStyleSheet(
            f"color:{DARK.text_tertiary};font-size:10px;"
        )
        configuration.content.addWidget(self.ftp_status)
        self._install_method_changed()

        progress_card = SurfaceCard()
        progress_title = QLabel("Deployment status")
        progress_title.setStyleSheet("font-size:14px;font-weight:700;")
        progress_card.content.addWidget(progress_title)
        self.status = QLabel(
            "RommHeld will validate the required assets, fetch the ROM and artwork from RomM, build the CIA locally, then hand it to the selected installation method."
        )
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color:{DARK.text_secondary};")
        progress_card.content.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        progress_card.content.addWidget(self.progress)

        self.deploy = AccentButton("Package and Deploy", accent)
        self.cancel = QPushButton("Cancel")
        self.cancel.setEnabled(False)
        self.deploy.clicked.connect(self.start)
        self.cancel.clicked.connect(self.cancel_deploy)

        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(self.cancel)
        actions.addWidget(self.deploy)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        layout.addLayout(header)
        layout.addWidget(assets)
        layout.addWidget(configuration)
        layout.addWidget(progress_card)
        layout.addLayout(actions)

    def _choose_boot_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose extracted AGB_FIRM boot logo",
            self.boot_logo_edit.text(),
        )
        if path:
            self.boot_logo_edit.setText(path)
            self._save_assets()

    def _choose_donor_banner(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose extracted GBA Virtual Console donor banner",
            self.donor_banner_edit.text(),
        )
        if path:
            self.donor_banner_edit.setText(path)
            self._save_assets()

    def _save_assets(self) -> bool:
        boot = Path(self.boot_logo_edit.text()).expanduser()
        if not boot.is_file():
            return False
        donor: Path | None = None
        if self.donor_banner_edit.text().strip():
            donor = Path(self.donor_banner_edit.text()).expanduser()
            if not donor.is_file():
                return False
        self.config = save_gba_vc_asset_paths(
            self.config,
            boot_logo=boot,
            donor_banner=donor,
        )
        return True

    def _install_method_changed(self) -> None:
        method = str(self.install_method_combo.currentData())
        is_fbi = method == "fbi"
        self.three_ds_ip_edit.setEnabled(is_fbi)
        if is_fbi:
            self.install_hint.setText(
                "On the 3DS open FBI → Remote Install → Receive URLs over the network. "
                "RommHeld serves the generated CIA directly and temporarily opens a narrowly scoped firewall rule when supported."
            )
        else:
            self.install_hint.setText(
                "FTP copies the generated CIA to the configured 3DS destination. Open the CIA in FBI afterward to install it."
            )

    def _save_3ds_ip(self) -> None:
        ip = self.three_ds_ip_edit.text().strip()
        devices = self.config.setdefault("devices", {})
        device = devices.setdefault("3ds", {})
        device["ip"] = ip
        save_config(self.config)

    def start(self) -> None:
        platform = (self.game.platform_slug or self.game.platform).strip().lower()
        if platform != "gba":
            QMessageBox.warning(
                self,
                "Unsupported Virtual Console target",
                "RommHeld currently has a real CIA injector only for GBA. Use RetroArch for this title until a platform-specific injector is implemented.",
            )
            return

        boot = Path(self.boot_logo_edit.text()).expanduser()
        if not boot.is_file():
            QMessageBox.warning(
                self,
                "AGB_FIRM boot logo required",
                "Choose a valid boot-logo region extracted from a GBA Virtual Console title you own. RommHeld will not generate a blank substitute because that can produce a CIA that crashes on real hardware.",
            )
            return
        if self.target_key == "vc_cia":
            donor = Path(self.donor_banner_edit.text()).expanduser()
            if not donor.is_file():
                QMessageBox.warning(
                    self,
                    "GBA VC donor banner required",
                    "Choose an extracted banner from a real GBA Virtual Console title. This is what provides the expected rotating Virtual Console box presentation on HOME Menu.",
                )
                return
        if not self._save_assets():
            QMessageBox.warning(
                self, "Invalid GBA VC assets", "One of the selected asset paths is invalid."
            )
            return

        method = str(self.install_method_combo.currentData())
        saved = self.config.get("devices", {}).get("3ds", {})
        if method == "ftp" and not str(saved.get("host", "")).strip():
            QMessageBox.warning(
                self,
                "3DS FTP not configured",
                "Configure the Nintendo 3DS FTP host first.",
            )
            return
        if method == "fbi" and not self.three_ds_ip_edit.text().strip():
            QMessageBox.warning(
                self,
                "3DS IP required",
                "Open FBI → Remote Install → Receive URLs over the network and enter the IP shown there.",
            )
            return
        self._save_3ds_ip()
        self.progress.setValue(0)
        self.status.setText("Preparing deployment…")
        self.deploy.setEnabled(False)
        self.install_method_combo.setEnabled(False)
        self.three_ds_ip_edit.setEnabled(False)
        self.cancel.setEnabled(True)
        self.worker = GbaCiaDeployWorker(
            self.config,
            self.game,
            self.target_key,
            self.destination_edit.text(),
            method,
            self.three_ds_ip_edit.text(),
        )
        self.worker.progress.connect(self.progress.setValue)
        self.worker.status_changed.connect(self.status.setText)
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _completed(self, result: str, destination: str) -> None:
        messages = {
            "copied": f"CIA copied and verified at {destination}.",
            "resumed": f"CIA resumed and verified at {destination}.",
            "skipped": f"CIA already exists at {destination} with the same size.",
            "different": f"A different-size CIA exists at {destination}; nothing was overwritten.",
            "fbi": "CIA was delivered to FBI. Complete or confirm the installation on the Nintendo 3DS.",
        }
        self.progress.setValue(100)
        self.status.setText(messages.get(result, result))
        if result == "different":
            QMessageBox.warning(
                self, "Existing CIA protected", self.status.text()
            )

    def _failed(self, message: str) -> None:
        self.status.setText(f"Deployment failed: {message}")

    def _finished(self) -> None:
        self.worker = None
        self.deploy.setEnabled(True)
        self.install_method_combo.setEnabled(True)
        self.cancel.setEnabled(False)
        self._install_method_changed()

    def cancel_deploy(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.cancel.setEnabled(False)
            self.status.setText("Cancelling and cleaning up…")

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        super().closeEvent(event)
