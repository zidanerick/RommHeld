#!/usr/bin/env python3
"""RommHeld application launcher."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from romm_vita_manager.config import load_config
from romm_vita_manager.console_selector import PlatformSelectorDialog
from romm_vita_manager.library_sources import get_library_source
from romm_vita_manager.romm_startup import RomMStartupVerifier
from romm_vita_manager.theme import apply_application_theme
from romm_vita_manager.workspace_dashboard import WorkspaceDashboardWindow


ACTIVE_WORKSPACES = {"vita", "3ds", "ds"}


def _workspace_is_configured(config: dict) -> bool:
    """Return whether normal startup can enter the saved workspace directly."""
    if not bool(config.get("setup_complete")):
        return False
    if str(config.get("active_console", "")).strip().lower() not in ACTIVE_WORKSPACES:
        return False

    source = get_library_source(config)
    if source.mode == "local":
        return bool(source.local_root) and Path(source.local_root).expanduser().is_dir()
    if source.mode == "romm_api":
        return bool(source.romm_url.strip() and source.api_token.strip())
    return False


def _run_selector(config: dict) -> bool:
    selector = PlatformSelectorDialog(config)
    verifier: RomMStartupVerifier | None = None

    source = get_library_source(config)
    if source.mode == "romm_api" and source.romm_url.strip() and source.api_token.strip():
        verifier = RomMStartupVerifier(source.romm_url, source.api_token, selector)
        verifier.succeeded.connect(selector.source_status.setText)
        verifier.failed.connect(
            lambda message: selector.source_status.setText(f"RomM unavailable • {message}")
        )
        QTimer.singleShot(0, verifier.start)

    accepted = selector.exec() == selector.DialogCode.Accepted
    if verifier is not None and verifier.isRunning():
        if not accepted:
            verifier.requestInterruption()
        verifier.wait()
    return accepted


def main() -> None:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("RommHeld")
    app.setApplicationDisplayName("RommHeld")
    app.setApplicationVersion("1.0")
    apply_application_theme(app)

    config = load_config()
    if not _workspace_is_configured(config):
        if not _run_selector(config):
            return
        config = load_config()

    window = WorkspaceDashboardWindow(config)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
