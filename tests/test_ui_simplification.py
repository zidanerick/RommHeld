from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_placeholder_navigation_is_not_exposed() -> None:
    source = _source("romm_vita_manager/management_shell.py")

    assert 'if key in {"queue", "tools"}:' in source
    assert 'device_heading = QLabel("DEVICE")' in source
    assert 'QPushButton("Switch handheld")' in source


def test_workspace_only_exposes_core_destinations() -> None:
    source = _source("romm_vita_manager/workspace_dashboard.py")

    assert 'self.shell.add_section("Library"' in source
    assert 'self.shell.add_section("Device"' in source
    assert 'self.shell.add_section("Settings"' in source
    assert 'self.shell.add_section("Setup"' not in source
    assert 'self.shell.add_section("Queue"' not in source
    assert 'self.shell.add_section("Tools"' not in source
    assert 'setup = AccentButton("Vita setup", accent)' in source


def test_page_subtitles_are_contextual() -> None:
    source = _source("romm_vita_manager/management_shell.py")

    assert 'if section == "library":' in source
    assert 'if section == "device":' in source
    assert 'if section == "settings":' in source
    assert 'self.page_subtitle.setText(self._subtitle_for_section(key))' in source


def test_vita_copy_primary_action_lives_with_library_selection() -> None:
    source = _source("romm_vita_manager/local_library.py")

    assert 'self.copy_button = AccentButton(' in source
    assert '"Copy to Vita"' in source
    assert 'self.copy_button.clicked.connect(self.copy_selected)' in source
    assert 'self.transfer_status.setText(f"Transfer complete' in source


def test_local_library_filters_without_rescanning_each_keystroke() -> None:
    source = _source("romm_vita_manager/local_library.py")

    assert 'self.search.textChanged.connect(self._apply_filters)' in source
    assert 'self.platforms.currentIndexChanged.connect(self._apply_filters)' in source
    assert 'self.status_filter.currentIndexChanged.connect(self._apply_filters)' in source
    assert 'self.refresh_button.clicked.connect(self.refresh_library)' in source
    assert 'def _apply_filters(self) -> None:' in source
    assert 'self.games = list(scan_games(root))' in source
    assert 'STATUS_LABELS = {' in source
    assert 'self.source_label.setToolTip(str(self._library_root))' in source
    assert 'self.destination_label.setToolTip(str(path))' in source


def test_vita_ftp_guidance_uses_current_device_navigation() -> None:
    source = _source("romm_vita_manager/local_library.py")

    assert "Device → Send file" in source
    assert "Tools → Send file" not in source


def test_romm_connection_can_be_tested_from_settings() -> None:
    source = _source("romm_vita_manager/workspace_dashboard.py")

    assert 'self.settings_test_button = QPushButton("Test connection")' in source
    assert 'self.settings_test_button.clicked.connect(self._test_settings_romm)' in source
    assert 'RomMConnectionWorker(normalized, token)' in source
    assert 'worker.finished.connect(thread.quit)' in source
    assert 'worker.finished.connect(worker.deleteLater)' in source
    assert 'Finish the RomM connection test before switching handhelds.' in source


def test_configured_startup_skips_selector_without_requiring_library_online() -> None:
    source = _source("launcher.py")

    assert 'def _workspace_is_configured(config: dict) -> bool:' in source
    assert 'if not _workspace_is_configured(config):' in source
    assert 'window = WorkspaceDashboardWindow(config)' in source
    assert 'ACTIVE_WORKSPACES = {"vita", "3ds", "ds"}' in source
    assert 'return bool(source.local_root.strip())' in source
    assert 'Path(source.local_root).expanduser().is_dir()' not in source


def test_runtime_preference_is_persisted_and_3ds_ra_remains_selectable() -> None:
    source = _source("romm_vita_manager/workspace_dashboard.py")

    assert 'updated = set_device_preference(self._reload_config(), self.workspace_key, key)' in source
    assert 'save_config(updated)' in source
    assert 'self.statusBar().showMessage("Runtime preference saved.", 3000)' in source
    assert 'if self.workspace_key == "3ds" and option.key == "retroachievements":' in source
    assert 'radio.setEnabled(False)' not in source
    assert 'Prefer RetroArch where the selected 3DS platform exposes a supported RetroArch route.' in source


def test_shared_theme_keeps_keyboard_focus_visible() -> None:
    source = _source("romm_vita_manager/theme.py")

    assert "QPushButton:focus" in source
    assert 'QPushButton[quiet="true"]:focus' in source
    assert "QListWidget:focus, QListView:focus" in source
