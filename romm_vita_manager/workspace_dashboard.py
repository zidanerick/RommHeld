from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from .app import MainWindow as BaseMainWindow, SendFileDialog
from .config import load_config, save_config
from .console_selector import PlatformSelectorDialog
from .design_tokens import DARK
from .gba_vc_deploy import GbaVcDeployDialog
from .library_sources import LibrarySource, get_library_source, save_library_source
from .management_shell import ManagementShell, WORKSPACE_PROFILES
from .mappings import platform_label
from .preferences import get_device_preference, preference_options, set_device_preference
from .romm import scan_games
from .romm_api import normalize_romm_url
from .romm_remote import RomMRemoteGame
from .storage_validation import validate_storage
from .three_ds_library import ThreeDSLibraryWidget
from .three_ds_manager import ThreeDSManagerDialog
from .three_ds_setup import ThreeDSSetupDialog
from .ui import human_size
from .ui_components import AccentButton, SurfaceCard
from .vita import find_vita_mounts, free_space, total_space
from .vita_setup import VitaSetupDialog


class WorkspaceDashboardWindow(BaseMainWindow):
    """Single-window RommHeld workspace with console-aware sections.

    This class now owns the correctness behavior that previously lived in the
    temporary audited_workspace subclass. It still inherits the original Vita
    window while that library is being extracted, but there is only one active
    workspace implementation in the launcher path.
    """

    def __init__(self, config: dict):
        self.workspace_key = str(config.get("active_console", "vita"))
        if self.workspace_key not in WORKSPACE_PROFILES:
            self.workspace_key = "vita"
        self.legacy_central: QWidget | None = None
        self.three_ds_library: ThreeDSLibraryWidget | None = None
        super().__init__(config)

        self.legacy_central = self.takeCentralWidget()
        self.shell = ManagementShell(WORKSPACE_PROFILES[self.workspace_key], self)
        self.setCentralWidget(self.shell)
        self.shell.change_handheld_requested.connect(self.change_workspace)
        self.shell.navigation_requested.connect(self._section_changed)
        self._prepare_legacy_library()
        self._rebuild_workspace_sections()

    def _prepare_legacy_library(self) -> None:
        if self.legacy_central is None:
            return
        splitter = self._find_library_splitter()
        if splitter is not None and splitter.count() > 1:
            splitter.widget(1).setVisible(False)
            splitter.setSizes([1, 0])

        # These controls belong to the old all-in-one toolbar. Their current
        # equivalents live in the sidebar Device/Setup/Tools/Settings pages.
        for name in (
            "send_file_button",
            "three_ds_button",
            "vita_setup_button",
            "settings_button",
        ):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setVisible(False)

        if self.workspace_key == "vita":
            self.status_filter.setEnabled(True)
        else:
            self.status_filter.setCurrentIndex(0)
            self.status_filter.setEnabled(False)

    def _find_library_splitter(self):
        central = self.legacy_central
        if central is None or central.layout() is None:
            return None
        for index in range(central.layout().count()):
            item = central.layout().itemAt(index)
            widget = item.widget() if item else None
            if widget is not None and hasattr(widget, "count"):
                try:
                    if widget.count() >= 2:
                        return widget
                except TypeError:
                    continue
        return None

    def _section_changed(self, section: str) -> None:
        if section == "library":
            self.refresh_games()
        elif section == "device":
            self.refresh_device_page()
        elif section == "setup":
            self.refresh_setup_page()

    def _rebuild_workspace_sections(self) -> None:
        if self.three_ds_library is not None:
            # Trigger the library's explicit worker shutdown before removing it
            # from the stack during a handheld switch.
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
            self.shell.add_section("Library", self.legacy_central, persistent=True)

        self.shell.add_section("Device", self._build_device_page())
        self.shell.add_section("Setup", self._build_setup_page())
        self.shell.add_section("Queue", self._build_queue_page())
        self.shell.add_section("Tools", self._build_tools_page())
        self.shell.add_section("Settings", self._build_settings_page())
        self.shell.select_section("Library")

        # The 3DS library starts its own initial progressive load. Do not
        # immediately invalidate that generation by calling refresh_games().
        if self.workspace_key == "3ds":
            self.refresh_device_page()
            self.refresh_setup_page()
        else:
            self.refresh_workspace()

    # Backwards-compatible internal name while callers migrate.
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
            self.workspace_vita_status = QLabel("Detecting…")
            self.workspace_vita_space = QLabel("-")
            form = QFormLayout()
            form.setContentsMargins(0, 0, 0, 0)
            form.addRow("Connection", self.workspace_vita_status)
            form.addRow("Storage", self.workspace_vita_space)
            card.content.addLayout(form)
            card.content.addWidget(
                self._secondary(
                    "RommHeld detects mounted Vita storage and keeps VitaShell/RetroFlow deployment separate from emulator/runtime choices."
                )
            )

            actions = QHBoxLayout()
            refresh = QPushButton("Refresh")
            refresh.clicked.connect(self.refresh_device_page)
            send = QPushButton("Send file")
            send.clicked.connect(self.open_vita_send_file)
            copy = AccentButton("Copy selected games", accent)
            copy.clicked.connect(self.copy_selected)
            actions.addWidget(refresh)
            actions.addWidget(send)
            actions.addStretch()
            actions.addWidget(copy)
            card.content.addLayout(actions)

        elif self.workspace_key == "3ds":
            saved = self.config.get("devices", {}).get("3ds", {})
            host = str(saved.get("host", "")).strip()
            port = saved.get("port", 5000)
            self.workspace_3ds_status = QLabel("Configured" if host else "Not configured")
            self.workspace_3ds_endpoint = QLabel(f"ftp://{host}:{port}" if host else "Not configured")
            form = QFormLayout()
            form.setContentsMargins(0, 0, 0, 0)
            form.addRow("FTP", self.workspace_3ds_status)
            form.addRow("Endpoint", self.workspace_3ds_endpoint)
            card.content.addLayout(form)
            card.content.addWidget(
                self._secondary(
                    "FTP handles filesystem transfers. FBI Remote Install is offered when a deployment produces an installable CIA."
                )
            )
            actions = QHBoxLayout()
            setup = QPushButton("Setup")
            setup.clicked.connect(self.open_3ds_setup)
            manage = AccentButton("Open 3DS manager", accent)
            manage.clicked.connect(self.open_3ds)
            actions.addWidget(setup)
            actions.addStretch()
            actions.addWidget(manage)
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
            browse = QPushButton("Choose SD card")
            browse.clicked.connect(self.choose_ds_root)
            validate = AccentButton("Validate storage", accent)
            validate.clicked.connect(self.validate_ds_root)
            actions.addWidget(browse)
            actions.addStretch()
            actions.addWidget(validate)
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
                radio.setEnabled(False)
                radio.setToolTip(
                    "Current 3DS achievement routes are not exposed as a supported recommendation."
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

    def _build_setup_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        profile = WORKSPACE_PROFILES[self.workspace_key]

        setup_card = SurfaceCard()
        setup_card.content.addWidget(self._card_title(f"{profile.name} setup"))
        if self.workspace_key == "vita":
            setup_card.content.addWidget(
                self._secondary(
                    "Detect Vita software and prepare supported runtime packages. Frontends, emulators and achievement support remain separate capabilities."
                )
            )
            button = AccentButton("Open Vita Setup", profile.accent)
            button.clicked.connect(self.open_vita_setup)
        elif self.workspace_key == "3ds":
            setup_card.content.addWidget(
                self._secondary(
                    "Configure the 3DS connection and inspect the target environment without mixing transport settings into runtime selection."
                )
            )
            button = AccentButton("Open Nintendo 3DS Setup", profile.accent)
            button.clicked.connect(self.open_3ds_setup)
        else:
            setup_card.content.addWidget(
                self._secondary(
                    "Choose and validate the DS/flashcard SD root before adding target-specific deployment mappings."
                )
            )
            button = AccentButton("Validate DS Setup", profile.accent)
            button.clicked.connect(self.validate_ds_root)
        setup_card.content.addWidget(button)

        layout.addWidget(setup_card)
        layout.addWidget(self._runtime_preference_box())
        layout.addStretch(1)
        return page

    def _build_queue_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        card = SurfaceCard()
        card.content.addWidget(self._card_title("Transfer queue"))
        card.content.addWidget(
            self._secondary(
                "Transfers currently execute immediately. A persistent queue will appear here when retry, per-item state and resume behavior are unified behind the common transport layer."
            )
        )
        state = QLabel("Not available in this build")
        state.setStyleSheet(f"color:{DARK.text_tertiary};font-size:11px;font-weight:600;")
        card.content.addWidget(state)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_tools_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        card = SurfaceCard()
        card.content.addWidget(self._card_title("Tools"))

        if self.workspace_key == "vita":
            card.content.addWidget(self._secondary("Send a file outside the normal library deployment workflow."))
            button = AccentButton("Send file to Vita", WORKSPACE_PROFILES["vita"].accent)
            button.clicked.connect(self.open_vita_send_file)
            card.content.addWidget(button)
        elif self.workspace_key == "3ds":
            card.content.addWidget(
                self._secondary("Browse and transfer files directly through the configured Nintendo 3DS FTP connection.")
            )
            button = AccentButton("Open 3DS file manager", WORKSPACE_PROFILES["3ds"].accent)
            button.clicked.connect(self.open_3ds)
            card.content.addWidget(button)
        else:
            card.content.addWidget(
                self._secondary(
                    "DS tools currently operate on the selected flashcard/removable SD root. FTP is not assumed for DS targets."
                )
            )

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        source = get_library_source(self.config)
        source_card = SurfaceCard()
        source_card.content.addWidget(self._card_title("Library source"))
        source_card.content.addWidget(
            self._secondary("Choose where RommHeld reads library metadata and ROM content for this desktop installation.")
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

        save = AccentButton("Save library settings", WORKSPACE_PROFILES[self.workspace_key].accent)
        save.clicked.connect(self._save_settings_source)
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_row.addWidget(save)
        source_card.content.addLayout(save_row)

        layout.addWidget(source_card)
        layout.addWidget(self._runtime_preference_box())
        note = self._secondary(
            "RomM connection testing is available from the handheld selector. Credentials are currently stored in local application configuration until secure credential-store migration is implemented."
        )
        layout.addWidget(note)
        layout.addStretch(1)

        self._settings_source_visibility()
        self.settings_local_radio.toggled.connect(self._settings_source_visibility)
        return page

    def _settings_source_visibility(self) -> None:
        local = self.settings_local_radio.isChecked()
        self.settings_local_edit.setEnabled(local)
        self.settings_url_edit.setEnabled(not local)
        self.settings_token_edit.setEnabled(not local)

    def _browse_settings_local(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select local ROM directory", self.settings_local_edit.text()
        )
        if path:
            self.settings_local_edit.setText(path)

    def _save_settings_source(self) -> None:
        if self.settings_local_radio.isChecked():
            root = Path(self.settings_local_edit.text()).expanduser()
            if not root.is_dir():
                self.statusBar().showMessage("Local ROM directory does not exist.", 5000)
                return
            source = LibrarySource(mode="local", local_root=str(root))
        else:
            try:
                url = normalize_romm_url(self.settings_url_edit.text())
            except ValueError as exc:
                self.statusBar().showMessage(str(exc), 5000)
                return
            token = self.settings_token_edit.text().strip()
            if not token:
                self.statusBar().showMessage("Enter a RomM Client API Token.", 5000)
                return
            source = LibrarySource(mode="romm_api", romm_url=url, api_token=token)
        self.config = save_library_source(load_config(), source)
        save_config(self.config)
        self.romm_root = Path(self.config.get("romm_root", self.romm_root)).expanduser()
        self.statusBar().showMessage("Library settings saved.", 5000)
        self.refresh_games()

    def _runtime_preference_changed(self, checked: bool) -> None:
        if not checked:
            return
        radio = self.sender()
        if not isinstance(radio, QRadioButton):
            return
        try:
            updated = set_device_preference(
                load_config(), self.workspace_key, str(radio.property("preference_key"))
            )
            save_config(updated)
            self.config = updated
        except (TypeError, ValueError, OSError):
            return

    def refresh_games(self) -> None:
        if self.workspace_key == "3ds" and self.three_ds_library is not None:
            if self.three_ds_library.library_worker and self.three_ds_library.library_worker.isRunning():
                return
            self.three_ds_library.config = self._reload_config()
            self.three_ds_library.refresh_library()
            return

        source = get_library_source(load_config())
        if source.mode == "romm_api":
            self.games = []
            self.filtered_games = []
            self.game_list.clear()
            self.source_label.setText(
                "RomM server selected • this workspace still uses the legacy local-library view. "
                "No local library is substituted."
            )
            self.selection_label.setText("0 selected")
            return

        self.romm_root = Path(source.local_root or self.config.get("romm_root", "")).expanduser()
        self.games = scan_games(self.romm_root)
        current = self.platforms.currentText() if self.platforms.count() else "All platforms"
        self.platforms.blockSignals(True)
        self.platforms.clear()
        self.platforms.addItem("All platforms")
        self.platforms.addItems(
            sorted({g.source_platform for g in self.games}, key=lambda s: platform_label(s).lower())
        )
        idx = self.platforms.findText(current)
        self.platforms.setCurrentIndex(idx if idx >= 0 else 0)
        self.platforms.blockSignals(False)

        query = self.search.text().strip().lower()
        platform = self.platforms.currentText()
        wanted = self.status_filter.currentText()
        self.filtered_games = []
        for game in self.games:
            if query and query not in game.name.lower():
                continue
            if platform != "All platforms" and game.source_platform != platform:
                continue
            state = "NEW"
            if self.workspace_key == "vita":
                try:
                    state, _ = self.game_status(game)
                except Exception:
                    state = "UNKNOWN"
            if wanted == "Not installed" and state != "NEW":
                continue
            if wanted == "Installed" and state != "INSTALLED":
                continue
            if wanted == "Different" and state != "DIFFERENT":
                continue
            if wanted == "Unknown" and state != "UNKNOWN":
                continue
            self.filtered_games.append(game)

        self.game_list.clear()
        symbols = {"INSTALLED": "✓", "NEW": "↓", "DIFFERENT": "↻", "UNKNOWN": "?"}
        QListWidgetItem = __import__("PySide6.QtWidgets", fromlist=["QListWidgetItem"]).QListWidgetItem
        for game in self.filtered_games:
            if self.workspace_key == "vita":
                state, detail = self.game_status(game)
            else:
                state, detail = "UNKNOWN", "Target status managed in Device"
            item = QListWidgetItem(
                f"{symbols[state]} {game.name}\n"
                f"{platform_label(game.source_platform)} • {human_size(game.size)} • {detail}"
            )
            item.setData(Qt.ItemDataRole.UserRole, game)
            self.game_list.addItem(item)
        self.apply_view_mode()
        self.source_label.setText(
            f"{self.romm_root} • {len(self.filtered_games)} games shown • "
            f"{WORKSPACE_PROFILES[self.workspace_key].name} target"
        )
        self.update_summary()

    def game_status(self, game):
        from .ui import game_status

        if self.vita is None:
            return "UNKNOWN", "Vita not connected"
        return game_status(self.vita, game, self.mappings)

    def refresh_workspace(self) -> None:
        self.refresh_device_page()
        self.refresh_setup_page()
        self.refresh_games()

    def refresh_device_page(self) -> None:
        if self.workspace_key == "vita":
            mounts = find_vita_mounts()
            self.vita = mounts[0] if mounts else None
            if self.vita:
                self.workspace_vita_status.setText("Connected")
                self.workspace_vita_status.setToolTip(str(self.vita))
                try:
                    self.workspace_vita_space.setText(
                        f"{human_size(free_space(self.vita))} free of {human_size(total_space(self.vita))}"
                    )
                except OSError:
                    self.workspace_vita_space.setText("Connected, storage unavailable")
            else:
                self.workspace_vita_status.setText("Not detected")
                self.workspace_vita_space.setText("-")
        elif self.workspace_key == "3ds":
            saved = self.config.get("devices", {}).get("3ds", {})
            host = str(saved.get("host", "")).strip()
            port = saved.get("port", 5000)
            self.workspace_3ds_status.setText("Configured" if host else "Not configured")
            self.workspace_3ds_endpoint.setText(f"ftp://{host}:{port}" if host else "Not configured")
        else:
            root = str(self._reload_config().get("ds_sd_root", "")).strip()
            self.ds_root.setText(root if root else "No SD root selected")

        if not hasattr(self, "shell"):
            return
        if self.workspace_key == "vita":
            vita_text = "Connected" if self.vita is not None else "Not detected"
        else:
            vita_text = "Connected" if self._safe_vita_mounts() else "Not detected"
        saved = self.config.get("devices", {}).get("3ds", {})
        host = str(saved.get("host", "")).strip()
        three_ds_text = "FTP configured" if host else "Not configured"
        ds_root = str(self.config.get("ds_sd_root", "")).strip()
        ds_text = "SD selected" if ds_root else "Not configured"
        self.shell.set_device_statuses(vita_text, three_ds_text, ds_text)

    @staticmethod
    def _safe_vita_mounts():
        try:
            return find_vita_mounts()
        except OSError:
            return []

    def refresh_setup_page(self) -> None:
        return

    def change_workspace(self) -> None:
        dialog = PlatformSelectorDialog(self._reload_config(), self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        config = self._reload_config()
        key = str(config.get("active_console", self.workspace_key))
        if key not in WORKSPACE_PROFILES:
            return
        self.workspace_key = key
        self._prepare_legacy_library()
        self._rebuild_workspace_sections()

    def choose_ds_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select mounted DS flashcard SD root")
        if path:
            self.config["ds_sd_root"] = path
            save_config(self.config)
            self.ds_root.setText(path)
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
        self.ds_validation.setText(f"{result.kind} • confidence: {result.confidence}")

    def open_vita_send_file(self) -> None:
        SendFileDialog(self.vita, self).exec()

    def open_3ds(self, game: RomMRemoteGame | None = None, target_key: str | None = None) -> None:
        config = self._reload_config()
        if game is not None and target_key in {"native_gba", "vc_cia"}:
            GbaVcDeployDialog(config, game, target_key, self).exec()
            return

        source = get_library_source(config)
        library_root = Path(source.local_root).expanduser() if source.mode == "local" and source.local_root else None
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

    def open_3ds_setup(self) -> None:
        dialog = ThreeDSSetupDialog(self.config, self)
        result = dialog.exec()
        if result == 2:
            self.open_3ds()
        else:
            self.config = self._reload_config()
            self.refresh_device_page()

    @staticmethod
    def _reload_config() -> dict:
        return load_config()

    def closeEvent(self, event) -> None:
        if self.three_ds_library is not None:
            self.three_ds_library.close()
        super().closeEvent(event)


__all__ = ["WorkspaceDashboardWindow"]
