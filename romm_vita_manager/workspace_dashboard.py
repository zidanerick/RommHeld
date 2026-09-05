from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from .send_file_dialog import SendFileDialog
from .classic_vc_deploy import ClassicVcDeployDialog
from .config import load_config, reset_config, save_config
from .console_selector import PlatformSelectorDialog, RomMConnectionWorker
from .design_tokens import DARK
from .gba_vc_deploy import GbaVcDeployDialog
from .library_sources import LibrarySource, get_library_source, save_library_source
from .local_library import LocalLibraryWidget
from .local_storage_ui import MountedStorageDialog
from .management_shell import ManagementShell, WORKSPACE_PROFILES
from .preferences import get_device_preference, preference_options, set_device_preference
from .romm_api import normalize_romm_url
from .romm_remote import RomMRemoteGame
from .storage_validation import validate_3ds_sd, validate_storage
from .three_ds_library import ThreeDSLibraryWidget
from .three_ds_manager import ThreeDSManagerDialog
from .three_ds_readiness_ui import ThreeDSReadinessDialog
from .three_ds_setup import ThreeDSSetupDialog
from .ui_components import AccentButton, SurfaceCard
from .vita import find_vita_mounts, free_space, total_space
from .vita_library_support import human_size
from .vita_setup import VitaSetupDialog


class WorkspaceDashboardWindow(QMainWindow):
    """Single-window RommHeld workspace with console-aware sections.

    The active application shell is independent of the original Vita MainWindow.
    Library, device readiness and settings remain the stable top-level surfaces;
    target-specific setup and advanced tools are launched contextually from them.
    """

    def __init__(self, config: dict):
        super().__init__()
        self.config = dict(config)
        self.workspace_key = str(config.get("active_console", "vita"))
        if self.workspace_key not in WORKSPACE_PROFILES:
            self.workspace_key = "vita"

        self.vita: Path | None = None
        self.three_ds_library: ThreeDSLibraryWidget | None = None
        self._settings_romm_thread: QThread | None = None
        self._settings_romm_worker: RomMConnectionWorker | None = None
        self._settings_romm_verified = False
        self.local_library = LocalLibraryWidget(
            self.config,
            self.workspace_key if self.workspace_key != "3ds" else "vita",
            None,
            self,
        )

        self.resize(1250, 760)
        self.shell = ManagementShell(WORKSPACE_PROFILES[self.workspace_key], self)
        self.setCentralWidget(self.shell)
        self.shell.change_handheld_requested.connect(self.change_workspace)
        self.shell.navigation_requested.connect(self._section_changed)
        self._rebuild_workspace_sections()

    def _section_changed(self, section: str) -> None:
        if section == "library":
            self.refresh_games()
        elif section == "device":
            self.refresh_device_page()

    def _rebuild_workspace_sections(self) -> None:
        if self.three_ds_library is not None:
            self.three_ds_library.close()
            self.three_ds_library = None

        self.config = self._reload_config()
        profile = WORKSPACE_PROFILES[self.workspace_key]
        self.setWindowTitle(f"RommHeld • {profile.name}")
        self.shell.set_profile(profile)
        self.shell.clear_sections()

        if self.workspace_key == "3ds":
            self.three_ds_library = ThreeDSLibraryWidget(self.config, self.open_3ds, self)
            self.shell.add_section("Library", self.three_ds_library)
        else:
            self.local_library.set_config(self.config)
            self.local_library.set_target(
                self.workspace_key,
                self.vita if self.workspace_key == "vita" else None,
            )
            self.shell.add_section("Library", self.local_library, persistent=True)

        self.shell.add_section("Device", self._build_device_page())
        self.shell.add_section("Settings", self._build_settings_page())
        self.shell.select_section("Library")

        if self.workspace_key == "3ds":
            self.refresh_device_page()
        else:
            self.refresh_workspace()

    def _rebuild_workspace_tabs(self) -> None:
        self._rebuild_workspace_sections()

    def _card_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color:{DARK.text_primary};font-size:15px;font-weight:700;")
        return label

    def _secondary(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{DARK.text_secondary};")
        return label

    def _build_device_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        accent = WORKSPACE_PROFILES[self.workspace_key].accent

        card = SurfaceCard()
        card.content.addWidget(self._card_title("Device connection"))

        if self.workspace_key == "vita":
            saved_ftp = self.config.get("devices", {}).get("vita_ftp", {})
            ftp_host = str(saved_ftp.get("host", "")).strip()
            ftp_port = saved_ftp.get("port", 1337)
            self.workspace_vita_status = QLabel("Detecting…")
            self.workspace_vita_space = QLabel("-")
            self.workspace_vita_ftp = QLabel(
                f"ftp://{ftp_host}:{ftp_port}" if ftp_host else "Not configured"
            )
            self.workspace_vita_ftp.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            form = QFormLayout()
            form.setContentsMargins(0, 0, 0, 0)
            form.addRow("USB", self.workspace_vita_status)
            form.addRow("Storage", self.workspace_vita_space)
            form.addRow("FTP fallback", self.workspace_vita_ftp)
            card.content.addLayout(form)
            card.content.addWidget(
                self._secondary(
                    "VitaShell USB is preferred on a handheld Vita. VitaShell FTP is available for wireless transfers and PlayStation TV; configure its endpoint from Send file when USB is unavailable."
                )
            )

            actions = QHBoxLayout()
            refresh = QPushButton("Refresh")
            refresh.clicked.connect(self.refresh_device_page)
            self.workspace_vita_send_action = AccentButton("Send file / configure FTP", accent)
            self.workspace_vita_send_action.clicked.connect(self.open_vita_send_file)
            self.workspace_vita_setup_action = AccentButton("Vita setup", accent)
            self.workspace_vita_setup_action.clicked.connect(self.open_vita_setup)
            self.workspace_vita_send_action.set_emphasized(not bool(ftp_host))
            self.workspace_vita_setup_action.set_emphasized(bool(ftp_host))
            actions.addWidget(refresh)
            actions.addWidget(self.workspace_vita_send_action)
            actions.addStretch()
            actions.addWidget(self.workspace_vita_setup_action)
            card.content.addLayout(actions)

        elif self.workspace_key == "3ds":
            saved = self.config.get("devices", {}).get("3ds", {})
            host = str(saved.get("host", "")).strip()
            port = saved.get("port", 5000)
            stored_root = str(saved.get("storage_root", "")).strip()
            mounted_root = self._safe_3ds_storage_root(saved)
            self.workspace_3ds_storage = QLabel(
                str(mounted_root)
                if mounted_root is not None
                else "Unavailable"
                if stored_root
                else "Not configured"
            )
            self.workspace_3ds_storage.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            if stored_root:
                self.workspace_3ds_storage.setToolTip(stored_root)
            self.workspace_3ds_status = QLabel("Configured" if host else "Not configured")
            self.workspace_3ds_endpoint = QLabel(
                f"ftp://{host}:{port}" if host else "Not configured"
            )
            form = QFormLayout()
            form.setContentsMargins(0, 0, 0, 0)
            form.addRow("Mounted SD", self.workspace_3ds_storage)
            form.addRow("FTP", self.workspace_3ds_status)
            form.addRow("Endpoint", self.workspace_3ds_endpoint)
            card.content.addLayout(form)
            card.content.addWidget(
                self._secondary(
                    "A mounted SD or microSD card is the direct, offline filesystem route and is useful for large transfers or initial setup. ftpd is the live-console wireless route. Nintendo 3DS systems do not expose a standard USB mass-storage mode, so RommHeld treats a card-reader mount as direct storage rather than calling it USB."
                )
            )
            actions = QHBoxLayout()
            self.workspace_3ds_setup_action = AccentButton("Connection setup", accent)
            self.workspace_3ds_setup_action.clicked.connect(self.open_3ds_setup)
            storage = QPushButton("Mounted SD files")
            storage.clicked.connect(self.open_3ds_storage)
            readiness = QPushButton("Runtime readiness")
            readiness.clicked.connect(self.open_3ds_readiness)
            self.workspace_3ds_manage_action = AccentButton("Open 3DS manager", accent)
            self.workspace_3ds_manage_action.clicked.connect(self.open_3ds)
            route_ready = bool(host) or mounted_root is not None
            self.workspace_3ds_setup_action.set_emphasized(not route_ready)
            self.workspace_3ds_manage_action.set_emphasized(route_ready)
            actions.addWidget(self.workspace_3ds_setup_action)
            actions.addWidget(storage)
            actions.addWidget(readiness)
            actions.addStretch()
            actions.addWidget(self.workspace_3ds_manage_action)
            card.content.addLayout(actions)

        else:
            configured = str(self.config.get("ds_sd_root", "")).strip()
            self.ds_root = QLabel(configured if configured else "No SD root selected")
            self.ds_root.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.ds_validation = QLabel("Not validated")
            form = QFormLayout()
            form.setContentsMargins(0, 0, 0, 0)
            form.addRow("SD root", self.ds_root)
            form.addRow("Validation", self.ds_validation)
            card.content.addLayout(form)
            card.content.addWidget(
                self._secondary(
                    "DS deployment is removable-storage first. RommHeld validates the selected root conservatively instead of assuming a specific flashcard model."
                )
            )
            actions = QHBoxLayout()
            self.ds_browse_action = AccentButton("Choose SD card", accent)
            self.ds_browse_action.clicked.connect(self.choose_ds_root)
            self.ds_validate_action = AccentButton("Validate storage", accent)
            self.ds_validate_action.clicked.connect(self.validate_ds_root)
            self.ds_browse_action.set_emphasized(not bool(configured))
            self.ds_validate_action.set_emphasized(bool(configured))
            actions.addWidget(self.ds_browse_action)
            actions.addStretch()
            actions.addWidget(self.ds_validate_action)
            card.content.addLayout(actions)

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _runtime_preference_box(self) -> QWidget:
        card = SurfaceCard()
        card.content.addWidget(self._card_title("Runtime preference"))
        card.content.addWidget(
            self._secondary(
                "This changes recommendations only. RommHeld still checks whether the selected route is actually available for the game and target."
            )
        )
        selected = get_device_preference(self.config, self.workspace_key)
        for option in preference_options():
            radio = QRadioButton(option.label)
            radio.setProperty("preference_key", option.key)
            radio.setChecked(selected == option.key)
            if self.workspace_key == "3ds" and option.key == "retroachievements":
                radio.setToolTip(
                    "Prefer RetroArch where the selected 3DS platform exposes a supported RetroArch route. Dedicated-only targets keep their available runtime."
                )
            elif self.workspace_key == "ds" and option.key == "retroachievements":
                radio.setToolTip(
                    "Prefer a supported RetroArch/libretro DS core when achievements are the priority."
                )
            elif self.workspace_key == "vita" and option.key == "retroachievements":
                radio.setToolTip(
                    "Prefer RetroArch/libretro cores where the selected system/core supports achievements."
                )
            radio.toggled.connect(self._runtime_preference_changed)
            card.content.addWidget(radio)
        return card

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        source = get_library_source(self.config)
        self._settings_romm_verified = False
        source_card = SurfaceCard()
        source_card.content.addWidget(self._card_title("Library source"))
        source_card.content.addWidget(
            self._secondary(
                "Choose where RommHeld reads library metadata and ROM content for this desktop installation."
            )
        )

        self.settings_local_radio = QRadioButton("Local ROM directory")
        self.settings_romm_radio = QRadioButton("RomM server")
        group = QButtonGroup(source_card)
        group.addButton(self.settings_local_radio)
        group.addButton(self.settings_romm_radio)
        self.settings_local_radio.setChecked(source.mode == "local")
        self.settings_romm_radio.setChecked(source.mode == "romm_api")
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.settings_local_radio)
        mode_row.addWidget(self.settings_romm_radio)
        mode_row.addStretch()
        source_card.content.addLayout(mode_row)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setVerticalSpacing(8)

        local_row = QHBoxLayout()
        self.settings_local_edit = QLineEdit(source.local_root)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_settings_local)
        local_row.addWidget(self.settings_local_edit, 1)
        local_row.addWidget(browse)
        form.addRow("Local root", local_row)

        self.settings_url_edit = QLineEdit(source.romm_url)
        self.settings_url_edit.setPlaceholderText("https://romm.example.com")
        self.settings_token_edit = QLineEdit(source.api_token)
        self.settings_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.settings_token_edit.setPlaceholderText("Client API Token")
        form.addRow("RomM URL", self.settings_url_edit)
        form.addRow("Client API Token", self.settings_token_edit)
        source_card.content.addLayout(form)

        self.settings_source_status = QLabel()
        self.settings_source_status.setWordWrap(True)
        source_card.content.addWidget(self.settings_source_status)

        accent = WORKSPACE_PROFILES[self.workspace_key].accent
        self.settings_test_button = AccentButton("Test connection", accent)
        self.settings_test_button.clicked.connect(self._test_settings_romm)
        self.settings_save_button = AccentButton("Save library settings", accent)
        self.settings_save_button.clicked.connect(self._save_settings_source)
        save_row = QHBoxLayout()
        save_row.addWidget(self.settings_test_button)
        save_row.addStretch()
        save_row.addWidget(self.settings_save_button)
        source_card.content.addLayout(save_row)

        reset_card = SurfaceCard()
        reset_card.content.addWidget(self._card_title("Application setup"))
        reset_card.content.addWidget(
            self._secondary(
                "Reset saved handheld, library, device connection/storage and runtime-preference settings and return to first-run setup. ROMs, files on devices, package caches, Virtual Console donor caches and generated Title ID allocations are kept."
            )
        )
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_button = QPushButton("Reset RommHeld setup")
        reset_button.clicked.connect(self._reset_application_setup)
        reset_row.addWidget(reset_button)
        reset_card.content.addLayout(reset_row)

        layout.addWidget(source_card)
        layout.addWidget(self._runtime_preference_box())
        layout.addWidget(
            self._secondary(
                "Credentials are currently stored in local application configuration until secure credential-store migration is implemented."
            )
        )
        layout.addWidget(reset_card)
        layout.addStretch(1)

        self.settings_local_radio.toggled.connect(self._settings_source_visibility)
        self.settings_url_edit.textChanged.connect(self._settings_source_changed)
        self.settings_token_edit.textChanged.connect(self._settings_source_changed)
        self._settings_source_visibility()
        return page

    def _set_settings_source_state(self, state: str, text: str) -> None:
        colors = {
            "success": DARK.success,
            "error": DARK.error,
            "busy": DARK.warning,
            "neutral": DARK.text_secondary,
        }
        self.settings_source_status.setText(text)
        self.settings_source_status.setStyleSheet(
            f"color:{colors.get(state, DARK.text_secondary)};font-size:10px;"
        )

    def _settings_source_changed(self) -> None:
        if self.settings_romm_radio.isChecked() and not self._settings_test_running():
            self._settings_romm_verified = False
            self._set_settings_source_state(
                "neutral",
                "Test the RomM connection before saving if these credentials changed.",
            )
            self._update_settings_action_emphasis()

    def _settings_test_running(self) -> bool:
        return bool(self._settings_romm_thread and self._settings_romm_thread.isRunning())

    def _update_settings_action_emphasis(self) -> None:
        local = self.settings_local_radio.isChecked()
        if local:
            self.settings_test_button.set_emphasized(False)
            self.settings_save_button.set_emphasized(True)
            return
        self.settings_test_button.set_emphasized(not self._settings_romm_verified)
        self.settings_save_button.set_emphasized(self._settings_romm_verified)

    def _settings_source_visibility(self) -> None:
        local = self.settings_local_radio.isChecked()
        testing = self._settings_test_running()
        self.settings_local_edit.setEnabled(local and not testing)
        self.settings_url_edit.setEnabled(not local and not testing)
        self.settings_token_edit.setEnabled(not local and not testing)
        self.settings_test_button.setVisible(not local)
        self.settings_test_button.setEnabled(not local and not testing)
        self.settings_save_button.setEnabled(not testing)
        self._update_settings_action_emphasis()
        if testing:
            self.settings_test_button.setText("Testing…")
            self._set_settings_source_state("busy", "Testing RomM connection…")
        else:
            self.settings_test_button.setText("Test connection")
            if local:
                root = Path(self.settings_local_edit.text()).expanduser()
                self._set_settings_source_state(
                    "success" if root.is_dir() else "neutral",
                    "Local library ready" if root.is_dir() else "Choose an existing ROM directory",
                )
            elif not self.settings_source_status.text():
                self._set_settings_source_state(
                    "neutral",
                    "Test the RomM connection before saving if these credentials changed.",
                )

    def _reset_application_setup(self) -> None:
        if self._settings_test_running():
            self.statusBar().showMessage(
                "Finish the RomM connection test before resetting setup.", 4000
            )
            return
        answer = QMessageBox.question(
            self,
            "Reset RommHeld setup",
            "Reset saved handheld, library, device connection/storage and runtime-preference settings?\n\n"
            "ROMs, files on devices, package caches, Virtual Console donor caches and generated Title ID allocations will not be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.config = reset_config()
        except OSError as exc:
            QMessageBox.critical(self, "Unable to reset RommHeld", str(exc))
            return

        dialog = PlatformSelectorDialog(self.config, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            self.close()
            return
        config = self._reload_config()
        key = str(config.get("active_console", ""))
        if key not in WORKSPACE_PROFILES:
            self.close()
            return
        self.workspace_key = key
        self._rebuild_workspace_sections()
        self.statusBar().showMessage("RommHeld setup reset.", 3000)

    def _test_settings_romm(self) -> None:
        if self._settings_test_running():
            return
        url = self.settings_url_edit.text().strip()
        token = self.settings_token_edit.text().strip()
        if not url or not token:
            self._settings_romm_verified = False
            self._set_settings_source_state(
                "error",
                "Enter the RomM server URL and Client API Token first.",
            )
            self._update_settings_action_emphasis()
            return
        try:
            normalized = normalize_romm_url(url)
        except ValueError as exc:
            self._settings_romm_verified = False
            self._set_settings_source_state("error", str(exc))
            self._update_settings_action_emphasis()
            return
        self.settings_url_edit.setText(normalized)

        thread = QThread(self)
        worker = RomMConnectionWorker(normalized, token)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._settings_romm_test_succeeded)
        worker.failed.connect(self._settings_romm_test_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._settings_romm_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._settings_romm_thread = thread
        self._settings_romm_worker = worker
        self._settings_source_visibility()
        thread.start()

    def _settings_romm_test_succeeded(self, message: str) -> None:
        self._settings_romm_verified = True
        self._set_settings_source_state("success", message)
        self._update_settings_action_emphasis()

    def _settings_romm_test_failed(self, message: str) -> None:
        self._settings_romm_verified = False
        self._set_settings_source_state("error", f"RomM unavailable • {message}")
        self._update_settings_action_emphasis()

    def _settings_romm_thread_finished(self) -> None:
        self._settings_romm_worker = None
        self._settings_romm_thread = None
        self._settings_source_visibility()

    def _browse_settings_local(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select local ROM directory", self.settings_local_edit.text()
        )
        if path:
            self.settings_local_edit.setText(path)
            self._settings_source_visibility()

    def _save_settings_source(self) -> None:
        if self._settings_test_running():
            return
        mode = "local" if self.settings_local_radio.isChecked() else "romm_api"
        local_root = self.settings_local_edit.text().strip()
        romm_url = self.settings_url_edit.text().strip()
        token = self.settings_token_edit.text().strip()
        if mode == "local":
            root = Path(local_root).expanduser()
            if not root.is_dir():
                self._set_settings_source_state("error", "Choose an existing local ROM directory.")
                return
            local_root = str(root)
        else:
            try:
                romm_url = normalize_romm_url(romm_url)
            except ValueError as exc:
                self._set_settings_source_state("error", str(exc))
                return
            if not token:
                self._set_settings_source_state("error", "Enter the RomM Client API Token.")
                return
        source = LibrarySource(mode=mode, local_root=local_root, romm_url=romm_url, api_token=token)
        save_library_source(self.config, source)
        self.config = self._reload_config()
        self._rebuild_workspace_sections()

    def _runtime_preference_changed(self, checked: bool) -> None:
        if not checked:
            return
        radio = self.sender()
        if not isinstance(radio, QRadioButton):
            return
        key = str(radio.property("preference_key") or "")
        if not key:
            return
        try:
            updated = set_device_preference(self._reload_config(), self.workspace_key, key)
            save_config(updated)
        except (TypeError, ValueError, OSError) as exc:
            self.statusBar().showMessage(f"Unable to save runtime preference: {exc}", 5000)
            return
        self.config = updated
        self.local_library.set_config(updated)
        if self.three_ds_library is not None:
            self.three_ds_library.config = updated
        self.statusBar().showMessage("Runtime preference saved.", 3000)

    def copy_selected(self) -> None:
        if self.workspace_key != "vita":
            return
        self.local_library.copy_selected()

    def refresh_games(self) -> None:
        self.config = self._reload_config()
        if self.workspace_key == "3ds" and self.three_ds_library is not None:
            if (
                self.three_ds_library.library_worker
                and self.three_ds_library.library_worker.isRunning()
            ):
                return
            self.three_ds_library.config = self.config
            self.three_ds_library.refresh_library()
            return

        self.local_library.set_config(self.config)
        self.local_library.set_target(
            self.workspace_key,
            self.vita if self.workspace_key == "vita" else None,
        )
        self.local_library.refresh_library()

    def refresh_workspace(self) -> None:
        self.refresh_device_page()
        self.refresh_games()

    def refresh_device_page(self) -> None:
        self.config = self._reload_config()
        if self.workspace_key == "vita":
            mounts = self._safe_vita_mounts()
            self.vita = mounts[0] if mounts else None
            self.local_library.set_vita(self.vita)
            saved_ftp = self.config.get("devices", {}).get("vita_ftp", {})
            ftp_host = str(saved_ftp.get("host", "")).strip()
            ftp_port = saved_ftp.get("port", 1337)
            if self.vita:
                self.workspace_vita_status.setText("Mounted")
                self.workspace_vita_status.setToolTip(str(self.vita))
                try:
                    self.workspace_vita_space.setText(
                        f"{human_size(free_space(self.vita))} free of {human_size(total_space(self.vita))}"
                    )
                except OSError:
                    self.workspace_vita_space.setText("Mounted, storage unavailable")
            else:
                self.workspace_vita_status.setText("Not mounted")
                self.workspace_vita_space.setText("-")
            self.workspace_vita_ftp.setText(
                f"ftp://{ftp_host}:{ftp_port}" if ftp_host else "Not configured"
            )
            route_ready = self.vita is not None or bool(ftp_host)
            self.workspace_vita_send_action.set_emphasized(not route_ready)
            self.workspace_vita_setup_action.set_emphasized(route_ready)
        elif self.workspace_key == "3ds":
            saved = self.config.get("devices", {}).get("3ds", {})
            host = str(saved.get("host", "")).strip()
            port = saved.get("port", 5000)
            stored_root = str(saved.get("storage_root", "")).strip()
            mounted_root = self._safe_3ds_storage_root(saved)
            self.workspace_3ds_storage.setText(
                str(mounted_root)
                if mounted_root is not None
                else "Unavailable"
                if stored_root
                else "Not configured"
            )
            self.workspace_3ds_storage.setToolTip(stored_root)
            self.workspace_3ds_status.setText("Configured" if host else "Not configured")
            self.workspace_3ds_endpoint.setText(
                f"ftp://{host}:{port}" if host else "Not configured"
            )
            route_ready = bool(host) or mounted_root is not None
            self.workspace_3ds_setup_action.set_emphasized(not route_ready)
            self.workspace_3ds_manage_action.set_emphasized(route_ready)
        else:
            root = str(self.config.get("ds_sd_root", "")).strip()
            self.ds_root.setText(root if root else "No SD root selected")
            self.ds_browse_action.set_emphasized(not bool(root))
            self.ds_validate_action.set_emphasized(bool(root))

        if self.workspace_key == "vita":
            saved_ftp = self.config.get("devices", {}).get("vita_ftp", {})
            vita_text = (
                "USB mounted"
                if self.vita is not None
                else "FTP configured"
                if str(saved_ftp.get("host", "")).strip()
                else "Not detected"
            )
        else:
            vita_text = "Connected" if self._safe_vita_mounts() else "Not detected"
        saved = self.config.get("devices", {}).get("3ds", {})
        host = str(saved.get("host", "")).strip()
        mounted_root = self._safe_3ds_storage_root(saved)
        stored_root = str(saved.get("storage_root", "")).strip()
        three_ds_text = (
            "SD mounted"
            if mounted_root is not None
            else "FTP configured"
            if host
            else "SD unavailable"
            if stored_root
            else "Not configured"
        )
        ds_root = str(self.config.get("ds_sd_root", "")).strip()
        ds_text = "SD selected" if ds_root else "Not configured"
        self.shell.set_device_statuses(vita_text, three_ds_text, ds_text)

    @staticmethod
    def _safe_vita_mounts() -> list[Path]:
        try:
            return find_vita_mounts()
        except OSError:
            return []

    @staticmethod
    def _safe_3ds_storage_root(saved: dict) -> Path | None:
        raw = str(saved.get("storage_root", "")).strip()
        if not raw:
            return None
        root = Path(raw).expanduser()
        try:
            validation = validate_3ds_sd(root)
        except (OSError, ValueError):
            return None
        if validation.confidence not in {"medium", "high"}:
            return None
        return root.resolve()

    def change_workspace(self) -> None:
        if self._settings_test_running():
            self.statusBar().showMessage(
                "Finish the RomM connection test before switching handhelds.", 4000
            )
            return
        dialog = PlatformSelectorDialog(self._reload_config(), self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        config = self._reload_config()
        key = str(config.get("active_console", self.workspace_key))
        if key not in WORKSPACE_PROFILES:
            return
        self.workspace_key = key
        self._rebuild_workspace_sections()

    def choose_ds_root(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select mounted DS flashcard SD root"
        )
        if path:
            self.config["ds_sd_root"] = path
            save_config(self.config)
            self.ds_root.setText(path)
            self.ds_browse_action.set_emphasized(False)
            self.ds_validate_action.set_emphasized(True)
            self.validate_ds_root()

    def validate_ds_root(self) -> None:
        raw = str(self.ds_root.text()).strip()
        if not raw or raw == "No SD root selected":
            self.ds_validation.setText("Select the mounted SD card first.")
            return
        try:
            result = validate_storage(Path(raw))
        except (OSError, ValueError) as exc:
            self.ds_validation.setText(str(exc))
            return
        self.ds_validation.setText(
            f"{result.kind} • confidence: {result.confidence}"
        )

    def open_vita_send_file(self) -> None:
        if self.vita is None:
            self.refresh_device_page()
        SendFileDialog(self.vita, self).exec()
        self.config = self._reload_config()
        self.refresh_device_page()
        self.refresh_games()

    def open_3ds_storage(self) -> None:
        MountedStorageDialog(self._reload_config(), "3ds", "Nintendo 3DS", self).exec()
        self.config = self._reload_config()
        self.refresh_device_page()

    def open_3ds(
        self,
        game: RomMRemoteGame | None = None,
        target_key: str | None = None,
    ) -> None:
        config = self._reload_config()
        if game is not None and target_key == "vc_cia":
            platform = (game.platform_slug or game.platform).strip().lower()
            if platform in {"gb", "gbc", "nes", "gamegear", "snes"}:
                ClassicVcDeployDialog(config, game, self).exec()
                return
            if platform == "gba":
                GbaVcDeployDialog(config, game, target_key, self).exec()
                return
        if game is not None and target_key == "native_gba":
            GbaVcDeployDialog(config, game, target_key, self).exec()
            return

        source = get_library_source(config)
        library_root = (
            Path(source.local_root).expanduser()
            if source.mode == "local" and source.local_root
            else None
        )
        dialog = ThreeDSManagerDialog(config, library_root, self)
        dialog.exec()
        self.config = self._reload_config()
        self.refresh_device_page()
        if self.three_ds_library is not None:
            self.three_ds_library.config = self.config
            self.three_ds_library.refresh_library()

    def open_vita_setup(self) -> None:
        VitaSetupDialog(self.vita, self).exec()
        self.refresh_device_page()
        self.refresh_games()

    def open_3ds_setup(self) -> None:
        dialog = ThreeDSSetupDialog(self.config, self)
        result = dialog.exec()
        if result == 2:
            self.open_3ds()
        else:
            self.config = self._reload_config()
            self.refresh_device_page()

    def _choose_3ds_storage_root(self) -> Path | None:
        saved = self._reload_config().get("devices", {}).get("3ds", {})
        start = str(saved.get("storage_root", "")).strip()
        path = QFileDialog.getExistingDirectory(
            self,
            "Select mounted Nintendo 3DS SD-card root",
            start,
        )
        if not path:
            return None
        root = Path(path).expanduser()
        try:
            validation = validate_3ds_sd(root)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Invalid 3DS SD card", str(exc))
            return None
        if validation.confidence not in {"medium", "high"}:
            QMessageBox.warning(
                self,
                "3DS SD card not recognised",
                "The selected directory does not contain enough Nintendo 3DS SD-card markers. Select the card root that contains files such as boot.firm, boot.3dsx, luma/, or gm9/.",
            )
            return None
        cfg = self._reload_config()
        devices = dict(cfg.get("devices", {}))
        device = dict(devices.get("3ds", {}))
        device["storage_root"] = str(root.resolve())
        devices["3ds"] = device
        cfg["devices"] = devices
        save_config(cfg)
        self.config = cfg
        return root.resolve()

    def open_3ds_readiness(self) -> None:
        saved = self._reload_config().get("devices", {}).get("3ds", {})
        root = self._safe_3ds_storage_root(saved)
        if root is None:
            root = self._choose_3ds_storage_root()
        if root is None:
            return
        ThreeDSReadinessDialog(
            root,
            needs_ftp=True,
            needs_cia_install=False,
            parent=self,
        ).exec()
        self.config = self._reload_config()
        self.refresh_device_page()

    @staticmethod
    def _reload_config() -> dict:
        return load_config()

    def closeEvent(self, event) -> None:
        thread = self._settings_romm_thread
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait()
        if self.three_ds_library is not None:
            self.three_ds_library.close()
        super().closeEvent(event)


__all__ = ["WorkspaceDashboardWindow"]
