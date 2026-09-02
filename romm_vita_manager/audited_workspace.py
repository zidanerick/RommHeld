from __future__ import annotations

from pathlib import Path

from .app import ThreeDSSetupDialog
from .gba_vc_deploy import GbaVcDeployDialog
from .library_sources import get_library_source
from .management_shell import WORKSPACE_PROFILES
from .romm_remote import RomMRemoteGame
from .three_ds_library import ThreeDSLibraryWidget
from .three_ds_manager import ThreeDSManagerDialog
from .workspace_dashboard import WorkspaceDashboardWindow as BaseWorkspaceDashboardWindow


class WorkspaceDashboardWindow(BaseWorkspaceDashboardWindow):
    """Correctness layer for the transitional workspace UI."""

    def __init__(self, config: dict):
        self.three_ds_library: ThreeDSLibraryWidget | None = None
        super().__init__(config)

    def _prepare_legacy_library(self) -> None:
        super()._prepare_legacy_library()
        for name in ("send_file_button", "three_ds_button", "vita_setup_button", "settings_button"):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setVisible(False)

    def _rebuild_workspace_tabs(self) -> None:
        self.config = self._reload_config()
        profile = WORKSPACE_PROFILES[self.workspace_key]
        self.setWindowTitle(f"RommHeld • {profile.name}")
        self.shell.set_profile(profile)
        self.shell.clear_sections()

        if self.workspace_key == "3ds":
            self.three_ds_library = ThreeDSLibraryWidget(self.config, self.open_3ds, self)
            self.shell.add_section("Library", self.three_ds_library, persistent=True)
        else:
            self.three_ds_library = None
            self.shell.add_section("Library", self.legacy_central, persistent=True)

        self.shell.add_section("Device", self._build_device_page())
        self.shell.add_section("Setup", self._build_setup_page())
        self.shell.add_section("Queue", self._build_queue_page())
        self.shell.add_section("Tools", self._build_tools_page())
        self.shell.add_section("Settings", self._build_settings_page())

        # Selecting the first tab emits navigation_requested synchronously. For
        # the 3DS workspace the library widget already begins its initial load in
        # its constructor, so calling refresh_workspace here would immediately
        # invalidate that worker and leave the visible generation stale.
        self.shell.select_section("Library")
        if self.workspace_key == "3ds":
            self.refresh_device_page()
            self.refresh_setup_page()
        else:
            self.refresh_workspace()

    def refresh_games(self) -> None:
        if self.workspace_key == "3ds" and self.three_ds_library is not None:
            if self.three_ds_library.library_worker and self.three_ds_library.library_worker.isRunning():
                return
            self.three_ds_library.config = self._reload_config()
            self.three_ds_library.refresh_library()
            return
        super().refresh_games()
        if self.workspace_key == "vita":
            return
        for index in range(self.game_list.count()):
            item = self.game_list.item(index)
            text = item.text()
            if text.startswith("↓ "):
                item.setText("? " + text[2:])

    def refresh_device_page(self) -> None:
        super().refresh_device_page()
        if not hasattr(self, "shell"):
            return
        if self.workspace_key == "vita":
            vita_text = "Connected" if self.vita is not None else "Not detected"
        else:
            vita_text = "Connected" if self._safe_vita_mounts() else "Not detected"
        saved = self.config.get("devices", {}).get("3ds", {})
        host = str(saved.get("host", "")).strip()
        port = saved.get("port", 5000)
        three_ds_text = "FTP configured" if host else "Not configured"
        ds_root = str(self.config.get("ds_sd_root", "")).strip()
        ds_text = "SD selected" if ds_root else "Not configured"
        self.shell.set_device_statuses(vita_text, three_ds_text, ds_text)

    @staticmethod
    def _safe_vita_mounts():
        try:
            from .vita import find_vita_mounts
            return find_vita_mounts()
        except OSError:
            return []

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
        from .config import load_config
        return load_config()


__all__ = ["WorkspaceDashboardWindow"]