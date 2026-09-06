#!/usr/bin/env python3
"""RommHeld application launcher."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from romm_vita_manager.config import load_config
from romm_vita_manager.console_selector import PlatformSelectorDialog
from romm_vita_manager.library_sources import (
    get_library_source,
    workspace_supports_library_source,
)
from romm_vita_manager.theme import apply_application_theme
from romm_vita_manager.workspace_dashboard import WorkspaceDashboardWindow


ACTIVE_WORKSPACES = {"vita", "3ds", "ds"}


def _workspace_is_configured(config: dict) -> bool:
    """Return whether normal startup can enter the saved workspace directly.

    A temporarily unavailable library path or service is runtime state, not a
    reason to replay onboarding. An unsupported workspace/source pairing is a
    configuration problem, however, so onboarding must repair it rather than
    opening a Library surface that cannot use the saved provider.
    """
    if not bool(config.get("setup_complete")):
        return False
    workspace = str(config.get("active_console", "")).strip().lower()
    if workspace not in ACTIVE_WORKSPACES:
        return False

    source = get_library_source(config)
    if not workspace_supports_library_source(workspace, source.mode):
        return False
    if source.mode == "local":
        return bool(source.local_root.strip())
    if source.mode == "romm_api":
        return bool(source.romm_url.strip() and source.api_token.strip())
    return False


def _run_selector(config: dict) -> bool:
    # The selector owns explicit asynchronous RomM connection testing. Avoid a
    # second startup verifier thread whose completion would have to be waited on
    # when the dialog is dismissed, which can block the GUI during a network
    # timeout.
    selector = PlatformSelectorDialog(config)
    return selector.exec() == selector.DialogCode.Accepted


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
