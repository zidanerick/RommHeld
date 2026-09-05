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
    assert 'self.workspace_vita_setup_action = AccentButton("Vita setup", accent)' in source


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


def test_local_library_platform_filter_uses_friendly_labels_and_exact_keys() -> None:
    source = _source("romm_vita_manager/local_library.py")

    assert 'current = self.platforms.currentData() if self.platforms.count() else None' in source
    assert 'self.platforms.addItem("All platforms", None)' in source
    assert 'self.platforms.addItem(platform_label(key), key)' in source
    assert 'index = self.platforms.findData(current) if current is not None else 0' in source
    assert 'platform = self.platforms.currentData()' in source
    assert 'if platform is not None and game.source_platform != platform:' in source


def test_local_library_status_checks_are_cached_and_contextual() -> None:
    source = _source("romm_vita_manager/local_library.py")

    assert 'self._status_cache: dict[Path, tuple[str, str]] = {}' in source
    assert 'if wanted != "All games":' in source
    assert 'cached = self._status_cache.get(game.path)' in source
    assert 'self._status_cache[game.path] = result' in source
    assert 'show_status = (' in source
    assert 'and self.status_filter.currentText() != "All games"' in source
    assert 'if show_status:' in source
    assert 'Choose a status filter to inspect the current Vita destination state' in source
    assert '"Ready to copy"' in source
    assert '"Update available"' in source
    assert '"Destination unavailable"' in source
    assert '"Checked during FTP transfer"' not in source


def test_local_library_only_exposes_real_view_controls() -> None:
    source = _source("romm_vita_manager/local_library.py")

    assert 'self.view_mode' not in source
    assert '"Tiles"' not in source
    assert 'QListWidget.ViewMode.IconMode' not in source
    assert 'QSize' not in source


def test_local_library_empty_states_are_actionable() -> None:
    source = _source("romm_vita_manager/local_library.py")

    assert 'No local library is active. Choose a local source in Settings.' in source
    assert 'Reconnect it or choose another source in Settings.' in source
    assert 'Clear the search or adjust the filters.' in source


def test_vita_ftp_guidance_uses_current_device_navigation() -> None:
    source = _source("romm_vita_manager/local_library.py")

    assert "Device → Send file" in source
    assert "Tools → Send file" not in source


def test_device_primary_actions_follow_readiness() -> None:
    source = _source("romm_vita_manager/workspace_dashboard.py")
    components = _source("romm_vita_manager/ui_components.py")

    assert 'def set_emphasized(self, emphasized: bool) -> None:' in components
    assert 'self.workspace_vita_send_action.set_emphasized(not route_ready)' in source
    assert 'self.workspace_vita_setup_action.set_emphasized(route_ready)' in source
    assert 'self.workspace_3ds_setup_action.set_emphasized(not bool(host))' in source
    assert 'self.workspace_3ds_manage_action.set_emphasized(bool(host))' in source
    assert 'self.ds_browse_action.set_emphasized(not bool(root))' in source
    assert 'self.ds_validate_action.set_emphasized(bool(root))' in source
    assert 'self.ds_browse_action.set_emphasized(False)' in source
    assert 'self.ds_validate_action.set_emphasized(True)' in source


def test_romm_connection_can_be_tested_from_settings() -> None:
    source = _source("romm_vita_manager/workspace_dashboard.py")

    assert 'self.settings_test_button = AccentButton("Test connection", accent)' in source
    assert 'self.settings_test_button.clicked.connect(self._test_settings_romm)' in source
    assert 'RomMConnectionWorker(normalized, token)' in source
    assert 'worker.finished.connect(thread.quit)' in source
    assert 'worker.finished.connect(worker.deleteLater)' in source
    assert 'Finish the RomM connection test before switching handhelds.' in source


def test_settings_primary_action_follows_romm_verification_state() -> None:
    source = _source("romm_vita_manager/workspace_dashboard.py")

    assert 'self._settings_romm_verified = False' in source
    assert 'def _update_settings_action_emphasis(self) -> None:' in source
    assert 'self.settings_test_button.set_emphasized(not self._settings_romm_verified)' in source
    assert 'self.settings_save_button.set_emphasized(self._settings_romm_verified)' in source
    assert 'self._settings_romm_verified = True' in source
    assert 'self.settings_save_button.setEnabled(not testing)' in source


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
