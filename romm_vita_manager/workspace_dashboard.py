from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
    QButtonGroup,
)

from .app import MainWindow as BaseMainWindow, SendFileDialog, ThreeDSFtpDialog
from .config import load_config, save_config
from .console_selector import PlatformSelectorDialog
from .library_sources import LibrarySource, get_library_source, save_library_source
from .management_shell import ManagementShell, WORKSPACE_PROFILES
from .mappings import platform_label
from .romm import scan_games
from .romm_api import normalize_romm_url
from .storage_validation import validate_storage
from .three_ds_setup import ThreeDSSetupDialog
from .vita import find_vita_mounts, free_space, total_space
from .vita_setup import VitaSetupDialog
from .ui import human_size
from .preferences import get_device_preference, preference_options, set_device_preference


class WorkspaceDashboardWindow(BaseMainWindow):
    """Single-window RommHeld workspace with console-aware sections."""

    def __init__(self, config: dict):
        self.workspace_key = str(config.get("active_console", "vita"))
        if self.workspace_key not in WORKSPACE_PROFILES:
            self.workspace_key = "vita"
        self.legacy_central: QWidget | None = None
        super().__init__(config)

        self.legacy_central = self.takeCentralWidget()
        self.shell = ManagementShell(WORKSPACE_PROFILES[self.workspace_key], self)
        self.setCentralWidget(self.shell)
        self.shell.change_handheld_requested.connect(self.change_workspace)
        self.shell.navigation_requested.connect(self._section_changed)
        self._prepare_legacy_library()
        self._rebuild_workspace_tabs()

    def _prepare_legacy_library(self) -> None:
        if self.legacy_central is None:
            return
        splitter = self._find_library_splitter()
        if splitter is not None and splitter.count() > 1:
            splitter.widget(1).setVisible(False)
            splitter.setSizes([1, 0])
        for name in ("vita_setup_button", "settings_button"):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setVisible(False)

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

    def _rebuild_workspace_tabs(self) -> None:
        self.config = load_config()
        profile = WORKSPACE_PROFILES[self.workspace_key]
        self.setWindowTitle(f"RommHeld • {profile.name}")
        self.shell.set_profile(profile)
        self.shell.clear_sections()
        self._prepare_legacy_library()
        self.shell.add_section("Library", self.legacy_central, persistent=True)
        self.shell.add_section("Device", self._build_device_page())
        self.shell.add_section("Setup", self._build_setup_page())
        self.shell.add_section("Queue", self._build_queue_page())
        self.shell.add_section("Tools", self._build_tools_page())
        self.shell.add_section("Settings", self._build_settings_page())
        self.shell.select_section("Library")
        self.refresh_workspace()

    def _build_device_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        profile = WORKSPACE_PROFILES[self.workspace_key]
        heading = QLabel(profile.name.upper())
        heading.setStyleSheet(f"color:{profile.accent};font-size:20px;font-weight:900;")
        layout.addWidget(heading)

        if self.workspace_key == "vita":
            box = QGroupBox("Vita USB / VitaShell")
            form = QFormLayout(box)
            self.workspace_vita_status = QLabel("Detecting…")
            self.workspace_vita_space = QLabel("-")
            form.addRow("Connection:", self.workspace_vita_status)
            form.addRow("Storage:", self.workspace_vita_space)
            refresh = QPushButton("Refresh Vita")
            refresh.clicked.connect(self.refresh_device_page)
            form.addRow("", refresh)
            copy = QPushButton("Copy selected games → Vita")
            copy.clicked.connect(self.copy_selected)
            form.addRow("", copy)
            send = QPushButton("Send arbitrary file → Vita")
            send.clicked.connect(self.open_vita_send_file)
            form.addRow("", send)
            layout.addWidget(box)
        elif self.workspace_key == "3ds":
            box = QGroupBox("Nintendo 3DS FTP")
            form = QFormLayout(box)
            saved = self.config.get("devices", {}).get("3ds", {})
            host = str(saved.get("host", "")).strip()
            port = saved.get("port", 5000)
            self.workspace_3ds_status = QLabel("Configured" if host else "Not configured")
            self.workspace_3ds_endpoint = QLabel(f"ftp://{host}:{port}" if host else "Not configured")
            form.addRow("Status:", self.workspace_3ds_status)
            form.addRow("Endpoint:", self.workspace_3ds_endpoint)
            manage = QPushButton("Open FTP panel")
            manage.clicked.connect(self.open_3ds)
            form.addRow("", manage)
            setup = QPushButton("Open 3DS setup")
            setup.clicked.connect(self.open_3ds_setup)
            form.addRow("", setup)
            layout.addWidget(box)
        else:
            box = QGroupBox("Nintendo DS / R4 Flashcard SD")
            form = QFormLayout(box)
            configured = str(self.config.get("ds_sd_root", "")).strip()
            self.ds_root = QLabel(configured if configured else "No SD root selected")
            self.ds_validation = QLabel("Not validated")
            browse = QPushButton("Select mounted SD card")
            browse.clicked.connect(self.choose_ds_root)
            validate = QPushButton("Validate DS / flashcard layout")
            validate.clicked.connect(self.validate_ds_root)
            form.addRow("SD root:", self.ds_root)
            form.addRow("Validation:", self.ds_validation)
            form.addRow("", browse)
            form.addRow("", validate)
            layout.addWidget(box)

        layout.addStretch()
        return page

    def _runtime_preference_box(self) -> QGroupBox:
        box = QGroupBox("Runtime preference")
        layout = QVBoxLayout(box)
        selected = get_device_preference(self.config, self.workspace_key)
        for option in preference_options():
            radio = QRadioButton(option.label)
            radio.setProperty("preference_key", option.key)
            radio.setChecked(selected == option.key)
            if self.workspace_key == "3ds" and option.key == "retroachievements":
                radio.setEnabled(False)
                radio.setToolTip(
                    "Current RetroAchievements documentation lists Citra libretro cores for Nintendo 3DS as unsupported."
                )
            elif self.workspace_key == "ds" and option.key == "retroachievements":
                radio.setToolTip(
                    "Use a supported RetroArch/libretro DS core such as melonDS or melonDS DS when achievements are the priority."
                )
            elif self.workspace_key == "vita" and option.key == "retroachievements":
                radio.setToolTip(
                    "Prefer RetroArch/libretro cores where the selected system/core supports RetroAchievements."
                )
            radio.toggled.connect(self._runtime_preference_changed)
            layout.addWidget(radio)
        return box

    def _build_setup_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        profile = WORKSPACE_PROFILES[self.workspace_key]
        heading = QLabel("SETUP / RUNTIME")
        heading.setStyleSheet(f"color:{profile.accent};font-size:20px;font-weight:900;")
        layout.addWidget(heading)

        box = QGroupBox(profile.name)
        box_layout = QVBoxLayout(box)
        if self.workspace_key == "vita":
            label = QLabel(
                "Detect Vita software and prepare supported runtime packages. RetroAchievements is an emulator/core capability rather than a RetroFlow feature."
            )
            button = QPushButton("Open Vita Setup")
            button.clicked.connect(self.open_vita_setup)
        elif self.workspace_key == "3ds":
            label = QLabel(
                "Detect the 3DS SD layout and homebrew components. Native 3DS software and achievement capability are tracked separately."
            )
            button = QPushButton("Open 3DS Setup")
            button.clicked.connect(self.open_3ds_setup)
        else:
            label = QLabel(
                "Validate the R4/flashcard SD layout and prepare the DS runtime path. Achievement-capable RetroArch/libretro cores can be preferred independently of TWiLight Menu++."
            )
            button = QPushButton("Validate DS setup")
            button.clicked.connect(self.validate_ds_root)
        label.setWordWrap(True)
        box_layout.addWidget(label)
        box_layout.addWidget(self._runtime_preference_box())
        box_layout.addWidget(button)
        layout.addWidget(box)
        layout.addStretch()
        return page

    def _build_queue_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("TRANSFER QUEUE")
        title.setStyleSheet("font-size:20px;font-weight:900;")
        layout.addWidget(title)
        notice = QLabel(
            "Queue management is planned. The current transfer engine still executes selected transfers immediately, so no queue controls are exposed here yet."
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)
        disabled = QPushButton("Queue unavailable")
        disabled.setEnabled(False)
        layout.addWidget(disabled)
        layout.addStretch()
        return page

    def _build_tools_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("TOOLS")
        title.setStyleSheet("font-size:20px;font-weight:900;")
        layout.addWidget(title)
        if self.workspace_key == "vita":
            button = QPushButton("Send arbitrary file to Vita")
            button.clicked.connect(self.open_vita_send_file)
            layout.addWidget(button)
        elif self.workspace_key == "3ds":
            button = QPushButton("Open 3DS FTP file manager")
            button.clicked.connect(self.open_3ds)
            layout.addWidget(button)
        else:
            notice = QLabel(
                "DS tools currently operate on the mounted flashcard SD only. FTP is not assumed for an R4/flashcard."
            )
            notice.setWordWrap(True)
            layout.addWidget(notice)
        layout.addStretch()
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("SETTINGS")
        title.setStyleSheet("font-size:20px;font-weight:900;")
        layout.addWidget(title)

        source = get_library_source(self.config)
        box = QGroupBox("Library source")
        form = QFormLayout(box)
        self.settings_local_radio = QRadioButton("Local ROM directory")
        self.settings_romm_radio = QRadioButton("RomM server")
        group = QButtonGroup(box)
        group.addButton(self.settings_local_radio)
        group.addButton(self.settings_romm_radio)
        self.settings_local_radio.setChecked(source.mode == "local")
        self.settings_romm_radio.setChecked(source.mode == "romm_api")
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.settings_local_radio)
        mode_row.addWidget(self.settings_romm_radio)
        mode_row.addStretch()
        form.addRow("Mode:", mode_row)

        local_row = QHBoxLayout()
        self.settings_local_edit = QLineEdit(source.local_root)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_settings_local)
        local_row.addWidget(self.settings_local_edit, 1)
        local_row.addWidget(browse)
        form.addRow("Local root:", local_row)

        self.settings_url_edit = QLineEdit(source.romm_url)
        self.settings_token_edit = QLineEdit(source.api_token)
        self.settings_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("RomM URL:", self.settings_url_edit)
        form.addRow("Client API Token:", self.settings_token_edit)
        save = QPushButton("Save library settings")
        save.clicked.connect(self._save_settings_source)
        form.addRow("", save)
        layout.addWidget(box)
        layout.addWidget(self._runtime_preference_box())
        note = QLabel(
            "The RomM connection test is available on the startup selector. Remote library browsing is not substituted with the local library."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#8d96a4;")
        layout.addWidget(note)
        layout.addStretch()
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

    def refresh_games(self):
        source = get_library_source(load_config())
        if source.mode == "romm_api":
            self.games = []
            self.filtered_games = []
            self.game_list.clear()
            self.source_label.setText(
                "RomM server selected • remote library browsing is not enabled in this build. "
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
                state, detail = "UNKNOWN", "Target status managed in DEVICE"
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
                self.workspace_vita_status.setText(str(self.vita))
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
            root = str(load_config().get("ds_sd_root", "")).strip()
            self.ds_root.setText(root if root else "No SD root selected")

    def refresh_setup_page(self) -> None:
        return

    def change_workspace(self) -> None:
        dialog = PlatformSelectorDialog(load_config(), self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        config = load_config()
        key = str(config.get("active_console", self.workspace_key))
        if key not in WORKSPACE_PROFILES:
            return
        self.workspace_key = key
        self._rebuild_workspace_tabs()

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

    def open_3ds(self) -> None:
        dialog = ThreeDSFtpDialog(load_config(), self)
        dialog.exec()
        self.config = load_config()
        self.refresh_device_page()

    def open_vita_setup(self) -> None:
        VitaSetupDialog(self.vita, self).exec()
        self.refresh_device_page()

    def open_3ds_setup(self) -> None:
        ThreeDSSetupDialog(load_config(), self).exec()
        self.config = load_config()
        self.refresh_device_page()


__all__ = ["WorkspaceDashboardWindow"]
