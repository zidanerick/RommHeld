from __future__ import annotations

from PySide6.QtWidgets import QWidget

from .app import ThreeDSSetupDialog
from .library_sources import get_library_source
from .three_ds_manager import ThreeDSManagerDialog
from .workspace_dashboard import WorkspaceDashboardWindow as BaseWorkspaceDashboardWindow


class WorkspaceDashboardWindow(BaseWorkspaceDashboardWindow):
    """Small correctness layer for the transitional workspace UI."""

    def _prepare_legacy_library(self) -> None:
        super()._prepare_legacy_library()
        # Device actions belong to Device/Setup/Tools now, not the global Library toolbar.
        for name in ("send_file_button", "three_ds_button", "vita_setup_button", "settings_button"):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setVisible(False)

    def refresh_games(self) -> None:
        super().refresh_games()
        if self.workspace_key == "vita":
            return
        # We do not have installed-state detection for 3DS/DS yet, so never label
        # those games as NEW merely because they are present in the library.
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
            vita_mounts = self._safe_vita_mounts()
            vita_text = "Connected" if vita_mounts else "Not detected"

        saved = self.config.get("devices", {}).get("3ds", {})
        host = str(saved.get("host", "")).strip()
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

    def open_3ds(self) -> None:
        source = get_library_source(self._reload_config())
        library_root = Path(source.local_root).expanduser() if source.mode == "local" and source.local_root else None
        dialog = ThreeDSManagerDialog(load_config(), library_root, self)
        dialog.exec()
        self.config = self._reload_config()
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
        from .config import load_config
        return load_config()


__all__ = ["WorkspaceDashboardWindow"]
