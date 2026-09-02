from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .app import MainWindow as BaseMainWindow, SendFileDialog, ThreeDSFtpDialog
from .console_selector import PlatformSelectorDialog
from .config import load_config, save_config
from .mappings import platform_label
from .models import Game
from .romm import scan_games
from .three_ds_setup import ThreeDSSetupDialog
from .storage_validation import validate_storage
from .vita import find_vita_mounts, free_space, total_space
from .vita_setup import VitaSetupDialog
from .management_shell import ManagementShell, WORKSPACE_PROFILES
from .ui import STATUS_SYMBOLS, human_size, game_status


class WorkspaceDashboardWindow(BaseMainWindow):
    """Single-window RommHeld workspace with console-aware tabs."""

    def __init__(self, config: dict):
        self.workspace_key = str(config.get("active_console", "vita"))
        if self.workspace_key not in WORKSPACE_PROFILES:
            self.workspace_key = "vita"
        self._workspace_dialog = None
        self._active_setup_panel: QWidget | None = None
        super().__init__(config)

        legacy_central = self.takeCentralWidget()
        self.legacy_central = legacy_central
        self.setWindowTitle(f"RommHeld • {WORKSPACE_PROFILES[self.workspace_key].name}")

        self.shell = ManagementShell(WORKSPACE_PROFILES[self.workspace_key], self)
        self.setCentralWidget(self.shell)
        self.shell.change_handheld_requested.connect(self.change_workspace)
        self.shell.navigation_requested.connect(self._section_changed)

        if legacy_central is not None:
            self._configure_library_for_workspace()
            self.shell.add_section("Library", legacy_central)
        self.shell.add_section("Device", self._build_device_page())
        self.shell.add_section("Setup", self._build_setup_page())
        self.shell.add_section("Queue", self._build_queue_page())
        self.shell.add_section("Tools", self._build_tools_page())
        self.shell.add_section("Settings", self._build_settings_page())
        self.shell.select_section("Library")
        self.refresh_workspace()

    def _section_changed(self, section: str) -> None:
        if section == "library":
            self.refresh_games()
        elif section == "device":
            self.refresh_device_page()
        elif section == "setup":
            self.refresh_setup_page()

    def _configure_library_for_workspace(self) -> None:
        self.vita_setup_button.setVisible(self.workspace_key == "vita")
        splitter = self._library_splitter()
        if splitter is not None and splitter.count() > 1:
            # The old right-hand device panel is now represented by the DEVICE tab.
            splitter.widget(1).setVisible(False)
            splitter.setSizes([1, 0])

    def _library_splitter(self):
        central = self.legacy_central
        if central is None or central.layout() is None:
            return None
        layout = central.layout()
        for index in range(layout.count()):
            item = layout.itemAt(index)
            widget = item.widget() if item else None
            if widget is not None and hasattr(widget, "count"):
                try:
                    if widget.count() >= 2:
                        return widget
                except TypeError:
                    pass
        return None

    def refresh_games(self):
        if self.workspace_key == "vita":
            return super().refresh_games()

        self.games = scan_games(self.romm_root)
        current = self.platforms.currentText()
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
        self.filtered_games = []
        for game in self.games:
            if query and query not in game.name.lower():
                continue
            if platform != "All platforms" and game.source_platform != platform:
                continue
            if self.status_filter.currentText() != "All games":
                # Non-Vita installation status is deliberately not guessed.
                continue
            self.filtered_games.append(game)

        self.game_list.clear()
        for game in self.filtered_games:
            item = __import__("PySide6.QtWidgets", fromlist=["QListWidgetItem"]).QListWidgetItem(
                f"{STATUS_SYMBOLS['UNKNOWN']} {game.name}\n"
                f"{platform_label(game.source_platform)} • {human_size(game.size)} • "
                f"Target status managed in {WORKSPACE_PROFILES[self.workspace_key].name} DEVICE tab"
            )
            item.setData(Qt.ItemDataRole.UserRole, game)
            self.game_list.addItem(item)
        self.apply_view_mode()
        self.source_label.setText(
            f"{self.romm_root} • {len(self.filtered_games)} games shown • "
            f"{WORKSPACE_PROFILES[self.workspace_key].name} target"
        )
        self.update_summary()

    def _build_device_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        profile = WORKSPACE_PROFILES[self.workspace_key]

        heading = QLabel(profile.name.upper())
        heading.setStyleSheet(f"color:{profile.accent};font-size:18px;font-weight:900;")
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
            self.workspace_3ds_endpoint = QLabel("Not configured")
            saved = self.config.get("devices", {}).get("3ds", {})
            host = str(saved.get("host", "")).strip()
            port = saved.get("port", 5000)
            self.workspace_3ds_endpoint.setText(f"ftp://{host}:{port}" if host else "Not configured")
            form.addRow("Endpoint:", self.workspace_3ds_endpoint)
            form.addRow("Mode:", QLabel("FTP transport"))
            manage = QPushButton("Open FTP panel")
            manage.clicked.connect(self.open_3ds)
            form.addRow("", manage)
            layout.addWidget(box)
        else:
            box = QGroupBox("Nintendo DS / Flashcard SD")
            form = QFormLayout(box)
            self.ds_root = QLabel("No SD root selected")
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

    def _build_setup_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        profile = WORKSPACE_PROFILES[self.workspace_key]
        heading = QLabel("SETUP / RUNTIME")
        heading.setStyleSheet(f"color:{profile.accent};font-size:18px;font-weight:900;")
        layout.addWidget(heading)

        box = QGroupBox("Active console")
        box_layout = QVBoxLayout(box)
        description = {
            "vita": "Detect Vita runtimes, RetroFlow/Adrenaline packages and RetroAchievements-oriented RetroArch paths.",
            "3ds": "Detect Luma3DS, FBI, Universal-Updater, TWiLight Menu++, open_agb_firm and related 3DS components.",
            "ds": "Validate the flashcard SD layout and identify TWiLight Menu++ / nds-bootstrap indicators without assuming a 3DS install.",
        }[self.workspace_key]
        label = QLabel(description)
        label.setWordWrap(True)
        box_layout.addWidget(label)

        if self.workspace_key == "vita":
            button = QPushButton("Open Vita Setup")
            button.clicked.connect(self.open_vita_setup)
        elif self.workspace_key == "3ds":
            button = QPushButton("Open 3DS Setup")
            button.clicked.connect(self.open_3ds_setup)
        else:
            button = QPushButton("Validate DS setup")
            button.clicked.connect(self.validate_ds_root)
        box_layout.addWidget(button)
        layout.addWidget(box)

        if self.workspace_key == "vita":
            ra = QGroupBox("RetroAchievements")
            ra_layout = QVBoxLayout(ra)
            text = QLabel(
                "RetroAchievements is treated as an emulator/core capability, not a RetroFlow capability. "
                "When achievements are selected as the priority, the configuration should favour RetroArch/libretro where supported."
            )
            text.setWordWrap(True)
            ra_layout.addWidget(text)
            layout.addWidget(ra)
        elif self.workspace_key == "3ds":
            components = QLabel("3DS setup components: Luma3DS • FBI • Universal-Updater • TWiLight Menu++ • open_agb_firm")
            components.setWordWrap(True)
            layout.addWidget(components)
        else:
            components = QLabel("DS indicators: _nds/ • nds-bootstrap • TWiLightMenu • BOOT.NDS • R4.dat • TTMenu")
            components.setWordWrap(True)
            layout.addWidget(components)

        layout.addStretch()
        return page

    def _build_queue_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("TRANSFER QUEUE")
        title.setStyleSheet("font-size:18px;font-weight:900;")
        layout.addWidget(title)
        label = QLabel(
            "The current transfer engine runs an immediate selection. A persistent multi-device queue is planned; "
            "this page intentionally does not pretend that queueing already exists."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addWidget(QLabel("Current workspace: " + WORKSPACE_PROFILES[self.workspace_key].name))
        layout.addStretch()
        return page

    def _build_tools_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("TOOLS")
        title.setStyleSheet("font-size:18px;font-weight:900;")
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
            label = QLabel(
                "DS tools are intentionally limited to mounted-SD validation for now. "
                "No FTP transport is assumed for a flashcard."
            )
            label.setWordWrap(True)
            layout.addWidget(label)
        layout.addStretch()
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("SETTINGS")
        title.setStyleSheet("font-size:18px;font-weight:900;")
        layout.addWidget(title)
        source = self.config.get("library_source", {})
        layout.addWidget(QLabel(f"Library source: {source.get('mode', 'local')}"))
        layout.addWidget(QLabel(f"Active handheld: {WORKSPACE_PROFILES[self.workspace_key].name}"))
        edit = QPushButton("Open settings editor")
        edit.clicked.connect(self.open_settings)
        layout.addWidget(edit)
        layout.addStretch()
        return page

    def refresh_workspace(self) -> None:
        self._configure_library_for_workspace()
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
                    total = total_space(self.vita)
                    free = free_space(self.vita)
                    self.workspace_vita_space.setText(
                        f"{human_size(free)} free of {human_size(total)}"
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
            self.workspace_3ds_endpoint.setText(f"ftp://{host}:{port}" if host else "Not configured")

    def refresh_setup_page(self) -> None:
        if self._active_setup_panel is not None:
            self._active_setup_panel.update()

    def change_workspace(self) -> None:
        dialog = PlatformSelectorDialog(load_config(), self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        config = load_config()
        key = str(config.get("active_console", self.workspace_key))
        if key not in WORKSPACE_PROFILES:
            return
        save_config({**config, "active_console": key})
        self.workspace_key = key
        self._rebuild_workspace_tabs()

    def _rebuild_workspace_tabs(self) -> None:
        profile = WORKSPACE_PROFILES[self.workspace_key]
        self.setWindowTitle(f"RommHeld • {profile.name}")
        self.shell.set_profile(profile)
        self.shell.clear_sections()
        self.config = load_config()
        self.romm_root = Path(self.config.get("romm_root", self.romm_root)).expanduser()
        self.mappings = self.config.get("platform_mappings", {})
        self.shell.add_section("Library", self.legacy_central)
        self.shell.add_section("Device", self._build_device_page())
        self.shell.add_section("Setup", self._build_setup_page())
        self.shell.add_section("Queue", self._build_queue_page())
        self.shell.add_section("Tools", self._build_tools_page())
        self.shell.add_section("Settings", self._build_settings_page())
        self.shell.select_section("Library")
        self.refresh_workspace()

    def choose_ds_root(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path = QFileDialog.getExistingDirectory(self, "Select mounted DS flashcard SD root")
        if path:
            self.ds_root.setText(path)
            self.config["ds_sd_root"] = path
            save_config(self.config)
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
        dialog = SendFileDialog(self.vita, self)
        dialog.exec()

    def open_3ds(self) -> None:
        dialog = ThreeDSFtpDialog(load_config(), self)
        dialog.exec()
        self.config = load_config()
        self.refresh_device_page()

    def open_vita_setup(self) -> None:
        dialog = VitaSetupDialog(self.vita, self)
        dialog.exec()
        self.refresh_device_page()

    def open_3ds_setup(self) -> None:
        dialog = ThreeDSSetupDialog(load_config(), self)
        dialog.exec()
        self.config = load_config()
        self.refresh_device_page()


