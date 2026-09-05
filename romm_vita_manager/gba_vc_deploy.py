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

from .config import save_config
from .design_tokens import DARK, brand_for_platform
from .fbi_remote_install import FBIUrlServer
from .firewall import FirewallError, FirewallRule, allow_temporary, remove_temporary
from .gba_assets import (
    configured_boot_logo,
    configured_donor_banner,
    extract_and_cache_gba_donor_assets,
)
from .gba_vc import build_native_gba_cia
from .hshop_catalog import HShopVcRelease, find_official_vc_release
from .romm_remote import RomMRemoteGame, download_artwork, download_rom
from .three_ds_ftp import ThreeDSFtpBackend, ThreeDSFtpSettings
from .three_ds_storage import ThreeDSMountedStorageBackend, configured_3ds_storage_root
from .three_ds_targets import default_destination
from .ui_components import AccentButton, SurfaceCard
from .vc_donors import configured_boot9_path, configured_donor_path
from .vc_runtime_profiles import guidance_for_family, runtime_guidance_summary
from .vc_title_id_registry import displayed_title_id, persist_registered_title_id


class HShopLookupWorker(QThread):
    completed = Signal(object)

    def __init__(self, title: str, platform_slug: str):
        super().__init__()
        self.title = title
        self.platform_slug = platform_slug

    def run(self) -> None:
        self.completed.emit(find_official_vc_release(self.title, self.platform_slug))


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
        *,
        display_title: str | None = None,
        publisher: str = "",
    ):
        super().__init__()
        self.config = config
        self.game = game
        self.target_key = target_key
        self.destination = destination
        self.install_method = install_method
        self.three_ds_ip = three_ds_ip.strip()
        self.display_title = (display_title or game.name).strip() or game.name
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

    def run(self) -> None:
        try:
            platform = (self.game.platform_slug or self.game.platform).strip().lower()
            if platform != "gba":
                raise ValueError(
                    f"{self.target_key} is currently implemented only for GBA titles. "
                    f"{self.game.name} is identified as {platform or 'an unknown platform'}."
                )

            boot_logo_path = configured_boot_logo(self.config)
            donor_banner_path = configured_donor_banner(self.config)
            if boot_logo_path is None:
                raise ValueError(
                    "GBA VC donor assets are not prepared. Configure a GBA Virtual Console donor CIA and boot9.bin first."
                )
            if self.target_key == "vc_cia" and donor_banner_path is None:
                raise ValueError(
                    "GBA VC donor assets are incomplete. Re-prepare the configured donor CIA."
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
                download_rom(
                    url,
                    token,
                    self.game,
                    self.temp_rom,
                    cancel_event=self.cancel_event,
                )
            except TimeoutError as exc:
                raise TimeoutError("Timed out downloading the ROM from RomM.") from exc
            self._check_cancelled()

            self.status_changed.emit("Fetching RomM artwork…")
            try:
                artwork = download_artwork(url, token, self.game.cover_url) if self.game.cover_url else None
            except TimeoutError as exc:
                raise TimeoutError("Timed out downloading artwork from RomM.") from exc
            if not artwork:
                raise ValueError("No usable RomM artwork is available for this title.")
            self._check_cancelled()

            self.status_changed.emit("Allocating a stable RommHeld Title ID…")
            self.config, title_id = persist_registered_title_id("gba", self.game.rom_id)
            self._check_cancelled()

            self.status_changed.emit("Packaging GBA CIA for AGB_FIRM…")
            cia = build_native_gba_cia(
                self.temp_rom.read_bytes(),
                artwork,
                boot_logo=boot_logo_path.read_bytes(),
                donor_banner=donor_banner_path.read_bytes() if donor_banner_path is not None else None,
                title_id=title_id,
                title_name=self.display_title,
                long_title=self.display_title,
                publisher=self.publisher,
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
                        raise ValueError("Enter the 3DS IP address shown by FBI Remote Install.")

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
                        self.status_changed.emit("No supported active firewall detected; continuing…")

                    self.fbi_server.start()
                    served_url = self.fbi_server.send_to_fbi(self.three_ds_ip, host=server_ip)
                    self.status_changed.emit(
                        f"FBI accepted the request. Serving the CIA from {served_url}. Confirm installation on the 3DS…"
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
                try:
                    self.backend.connect()
                except TimeoutError as exc:
                    raise TimeoutError("Timed out connecting to the 3DS FTP server.") from exc
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
                    raise TimeoutError("Timed out uploading the CIA to the 3DS FTP server.") from exc
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
                    self.status_changed.emit(f"Warning: could not remove temporary firewall rule: {exc}")
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
        self.hshop_worker: HShopLookupWorker | None = None
        self.official_release: HShopVcRelease | None = None
        self.setWindowTitle("Deploy GBA to Nintendo 3DS")
        self.resize(800, 760)
        self.setMinimumWidth(720)

        accent = brand_for_platform("3ds").accent

        header = QVBoxLayout()
        header.setSpacing(3)
        self.title_label = QLabel(game.name)
        self.title_label.setStyleSheet(f"color:{DARK.text_primary};font-size:22px;font-weight:700;")
        mode = "Native GBA (AGB_FIRM)" if target_key == "native_gba" else "GBA Virtual Console CIA"
        self.mode_label = QLabel(mode)
        self.mode_label.setStyleSheet(f"color:{accent};font-size:11px;font-weight:600;")
        header.addWidget(self.title_label)
        header.addWidget(self.mode_label)

        official = SurfaceCard()
        official_title = QLabel("Official Nintendo Virtual Console")
        official_title.setStyleSheet("font-size:14px;font-weight:700;")
        official.content.addWidget(official_title)
        self.official_status = QLabel("Checking hShop catalogue for an official GBA Virtual Console release…")
        self.official_status.setWordWrap(True)
        self.official_status.setStyleSheet(f"color:{DARK.text_secondary};font-size:10px;")
        official.content.addWidget(self.official_status)
        self.open_official_button = QPushButton("Open official release")
        self.open_official_button.setEnabled(False)
        self.open_official_button.clicked.connect(self._open_official_release)
        official_row = QHBoxLayout()
        official_row.addStretch()
        official_row.addWidget(self.open_official_button)
        official.content.addLayout(official_row)

        donor_card = SurfaceCard()
        donor_title = QLabel("GBA Virtual Console runtime")
        donor_title.setStyleSheet("font-size:14px;font-weight:700;")
        donor_card.content.addWidget(donor_title)
        self.donor_guidance = QLabel()
        self.donor_guidance.setWordWrap(True)
        self.donor_guidance.setStyleSheet(f"color:{DARK.text_secondary};font-size:10px;")
        donor_card.content.addWidget(self.donor_guidance)
        self._refresh_donor_guidance()

        assets_ready = configured_boot_logo(config) is not None and configured_donor_banner(config) is not None
        configured_donor = configured_donor_path(config, "gba")
        configured_boot9 = configured_boot9_path(config)
        self.donor_cia_edit = QLineEdit(str(configured_donor) if configured_donor else "")
        self.donor_cia_edit.setPlaceholderText("GBA Virtual Console donor (.cia)")
        self.boot9_edit = QLineEdit(str(configured_boot9) if configured_boot9 else "")
        self.boot9_edit.setPlaceholderText("boot9.bin or boot9_prot.bin")

        if assets_ready:
            donor_note = QLabel(
                "Ready — the required AGB_FIRM boot logo and animated VC banner are cached locally. "
                "The original donor CIA and boot9 dump are no longer needed for normal GBA deployments."
            )
            donor_note.setWordWrap(True)
            donor_note.setStyleSheet(f"color:{DARK.text_secondary};font-size:10px;")
            donor_card.content.addWidget(donor_note)
        else:
            donor_note = QLabel(
                "One-time setup: choose a genuine GBA Virtual Console donor CIA and your own boot9 dump. "
                "RommHeld extracts only the two reusable assets it needs and then forgets the source paths."
            )
            donor_note.setWordWrap(True)
            donor_note.setStyleSheet(f"color:{DARK.text_secondary};font-size:10px;")
            donor_card.content.addWidget(donor_note)

            donor_browse = QPushButton("Browse…")
            donor_browse.clicked.connect(self._choose_donor_cia)
            donor_row = QHBoxLayout()
            donor_row.addWidget(self.donor_cia_edit, 1)
            donor_row.addWidget(donor_browse)

            boot9_browse = QPushButton("Browse…")
            boot9_browse.clicked.connect(self._choose_boot9)
            boot9_row = QHBoxLayout()
            boot9_row.addWidget(self.boot9_edit, 1)
            boot9_row.addWidget(boot9_browse)

            donor_form = QFormLayout()
            donor_form.setContentsMargins(0, 0, 0, 0)
            donor_form.addRow("GBA VC donor", donor_row)
            donor_form.addRow("boot9 dump", boot9_row)
            donor_card.content.addLayout(donor_form)

        self.donor_status = QLabel()
        self.donor_status.setWordWrap(True)
        self.donor_status.setStyleSheet(f"color:{DARK.text_secondary};font-size:10px;")
        donor_card.content.addWidget(self.donor_status)
        if not assets_ready:
            prepare = QPushButton("Prepare donor assets")
            prepare.clicked.connect(self._prepare_donor_assets)
            prepare_row = QHBoxLayout()
            prepare_row.addStretch()
            prepare_row.addWidget(prepare)
            donor_card.content.addLayout(prepare_row)
        self._refresh_donor_status()

        configuration = SurfaceCard()
        configuration_title = QLabel("Delivery")
        configuration_title.setStyleSheet("font-size:14px;font-weight:700;")
        configuration.content.addWidget(configuration_title)

        self.title_id_edit = QLineEdit(displayed_title_id(config, "gba", game.rom_id).hex())
        self.title_id_edit.setReadOnly(True)
        self.title_id_edit.setToolTip(
            "Current RommHeld assignment, or the preferred GBA VC candidate if this title has not been deployed yet."
        )
        self.destination_edit = QLineEdit(default_destination("vc_cia", "gba", game.filename))
        self.destination_edit.setReadOnly(True)
        self.display_title_edit = QLineEdit(game.name)
        self.display_title_edit.setReadOnly(True)
        self.display_title_edit.setToolTip(
            "Uses the official hShop title spelling when a confident catalogue match exists."
        )
        self.publisher_edit = QLineEdit(game.publisher)
        self.publisher_edit.setReadOnly(True)
        self.publisher_edit.setPlaceholderText("Not available in RomM metadata")
        self.publisher_edit.setToolTip(
            "Publisher comes from RomM metadata when available. Unknown publishers are left blank instead of being labelled Homebrew."
        )

        saved = config.get("devices", {}).get("3ds", {})
        self.three_ds_ip_edit = QLineEdit(str(saved.get("ip", "")))
        self.three_ds_ip_edit.setPlaceholderText("3DS IP shown by FBI")
        self.three_ds_ip_edit.setToolTip("The IP shown by FBI > Remote Install > Receive URLs over the network.")
        self.three_ds_ip_edit.editingFinished.connect(self._save_3ds_ip)

        self.install_method_combo = QComboBox()
        self.install_method_combo.addItem("FBI Remote Install · Install directly", "fbi")
        self.install_method_combo.addItem("Mounted SD card · Copy CIA", "sd")
        self.install_method_combo.addItem("ftpd · Copy CIA", "ftp")
        self.install_method_combo.currentIndexChanged.connect(self._install_method_changed)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(9)
        form.addRow("Delivery method", self.install_method_combo)
        form.addRow("3DS IP", self.three_ds_ip_edit)
        form.addRow("Display title", self.display_title_edit)
        form.addRow("Publisher", self.publisher_edit)
        form.addRow("Title ID", self.title_id_edit)
        form.addRow("CIA destination", self.destination_edit)
        configuration.content.addLayout(form)

        self.install_hint = QLabel()
        self.install_hint.setWordWrap(True)
        self.install_hint.setStyleSheet(f"color:{DARK.text_secondary};font-size:10px;")
        configuration.content.addWidget(self.install_hint)
        self.copy_status = QLabel(
            "Mounted SD and ftpd copy the generated CIA only. Install copied CIAs later with FBI."
        )
        self.copy_status.setStyleSheet(f"color:{DARK.text_tertiary};font-size:10px;")
        configuration.content.addWidget(self.copy_status)
        self._install_method_changed()

        progress_card = SurfaceCard()
        progress_title = QLabel("Deployment status")
        progress_title.setStyleSheet("font-size:14px;font-weight:700;")
        progress_card.content.addWidget(progress_title)
        self.status = QLabel(
            "RommHeld prefers an official Nintendo VC release when hShop metadata finds a confident match. "
            "If no official release is available, the local donor-backed GBA injector remains available."
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
        layout.setSpacing(12)
        layout.addLayout(header)
        layout.addWidget(official)
        layout.addWidget(donor_card)
        layout.addWidget(configuration)
        layout.addWidget(progress_card)
        layout.addLayout(actions)

        self._start_hshop_lookup()

    def _refresh_donor_guidance(self) -> None:
        guidance = guidance_for_family("gba")
        self.donor_guidance.setText(runtime_guidance_summary(self.config, "gba"))
        self.donor_guidance.setToolTip("\n".join(guidance.details))

    def _start_hshop_lookup(self) -> None:
        self.hshop_worker = HShopLookupWorker(self.game.name, "gba")
        self.hshop_worker.completed.connect(self._hshop_lookup_completed)
        self.hshop_worker.finished.connect(self._hshop_lookup_finished)
        self.hshop_worker.start()

    def _hshop_lookup_completed(self, release: object) -> None:
        self.official_release = release if isinstance(release, HShopVcRelease) else None
        if self.official_release is None:
            self.official_status.setText(
                "No confident official GBA Virtual Console match was found in hShop metadata. "
                "The donor-backed injector is the preferred fallback."
            )
            self.open_official_button.setEnabled(False)
            return
        item = self.official_release
        self.display_title_edit.setText(item.title)
        details = [f"Official release found: {item.title}", item.platform]
        if item.region:
            details.append(item.region)
        if item.title_id:
            details.append(f"Title ID {item.title_id}")
        if item.product_code:
            details.append(item.product_code)
        self.official_status.setText(" • ".join(details) + ". Prefer this release over generating an injection.")
        self.open_official_button.setEnabled(True)

    def _hshop_lookup_finished(self) -> None:
        self.hshop_worker = None

    def _open_official_release(self) -> None:
        if self.official_release is not None:
            webbrowser.open(self.official_release.url)

    def _choose_donor_cia(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose GBA Virtual Console donor CIA",
            self.donor_cia_edit.text(),
            "Nintendo 3DS CIA (*.cia);;All files (*)",
        )
        if path:
            self.donor_cia_edit.setText(path)
            self._refresh_donor_status()

    def _choose_boot9(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose boot9 dump",
            self.boot9_edit.text(),
            "boot9 dump (*.bin);;All files (*)",
        )
        if path:
            self.boot9_edit.setText(path)
            self._refresh_donor_status()

    def _refresh_donor_status(self) -> None:
        logo = configured_boot_logo(self.config)
        banner = configured_donor_banner(self.config)
        if logo is not None and banner is not None:
            self.donor_status.setText("Ready — cached GBA VC runtime assets will be reused automatically.")
        elif self.donor_cia_edit.text().strip() and self.boot9_edit.text().strip():
            self.donor_status.setText("Donor and boot9 selected. RommHeld will extract the required assets locally.")
        else:
            self.donor_status.setText("Select a GBA VC donor CIA and boot9 dump once to prepare this runtime.")

    def _prepare_donor_assets(self) -> bool:
        donor = Path(self.donor_cia_edit.text()).expanduser()
        boot9 = Path(self.boot9_edit.text()).expanduser()
        if not donor.is_file() or not boot9.is_file():
            QMessageBox.warning(
                self,
                "GBA VC donor setup incomplete",
                "Choose a valid GBA Virtual Console donor CIA and boot9.bin/boot9_prot.bin dump.",
            )
            return False
        try:
            self.config, logo, banner = extract_and_cache_gba_donor_assets(self.config, donor, boot9)
        except Exception as exc:
            QMessageBox.warning(self, "Could not prepare GBA VC donor", str(exc))
            return False
        self.donor_cia_edit.clear()
        self.boot9_edit.clear()
        self._refresh_donor_guidance()
        self.donor_status.setText(
            f"Ready — cached {logo.name} and {banner.name}. Source paths were discarded and are no longer required."
        )
        return True

    def _ensure_donor_assets(self) -> bool:
        if configured_boot_logo(self.config) is not None and configured_donor_banner(self.config) is not None:
            return True
        return self._prepare_donor_assets()

    def _install_method_changed(self) -> None:
        method = str(self.install_method_combo.currentData())
        is_fbi = method == "fbi"
        self.three_ds_ip_edit.setEnabled(is_fbi)
        if is_fbi:
            self.install_hint.setText(
                "On the 3DS open FBI → Remote Install → Receive URLs over the network. "
                "RommHeld serves the generated CIA directly and temporarily opens a narrowly scoped firewall rule when supported."
            )
        elif method == "sd":
            self.install_hint.setText(
                "Copies the generated CIA to the validated mounted 3DS SD card. Eject the card cleanly, return it to the console, then install the CIA with FBI."
            )
        else:
            self.install_hint.setText(
                "ftpd copies the generated CIA to the configured 3DS destination while the console is running. Open the CIA in FBI afterward to install it."
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
        if not self._ensure_donor_assets():
            return

        method = str(self.install_method_combo.currentData())
        saved = self.config.get("devices", {}).get("3ds", {})
        if method == "ftp" and not str(saved.get("host", "")).strip():
            QMessageBox.warning(self, "3DS FTP not configured", "Configure the Nintendo 3DS FTP host first.")
            return
        if method == "sd" and configured_3ds_storage_root(self.config) is None:
            QMessageBox.warning(
                self,
                "3DS SD card not mounted",
                "Configure and mount a validated Nintendo 3DS SD card from the Device page first.",
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
            display_title=self.display_title_edit.text(),
            publisher=self.publisher_edit.text(),
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
            QMessageBox.warning(self, "Existing CIA protected", self.status.text())

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
        if self.hshop_worker is not None and self.hshop_worker.isRunning():
            self.hshop_worker.wait(2000)
        super().closeEvent(event)
