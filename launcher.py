#!/usr/bin/env python3
"""RommHeld application launcher."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from romm_vita_manager.audited_workspace import WorkspaceDashboardWindow
from romm_vita_manager.config import load_config
from romm_vita_manager.console_selector import PlatformSelectorDialog
from romm_vita_manager.library_sources import get_library_source
from romm_vita_manager.romm_startup import RomMStartupVerifier


def main() -> None:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("RommHeld")
    app.setApplicationVersion("1.0")

    config = load_config()
    selector = PlatformSelectorDialog(config)
    verifier: RomMStartupVerifier | None = None

    source = get_library_source(config)
    if source.mode == "romm_api" and source.romm_url.strip() and source.api_token.strip():
        verifier = RomMStartupVerifier(source.romm_url, source.api_token, selector)
        verifier.succeeded.connect(selector.source_status.setText)
        verifier.failed.connect(lambda message: selector.source_status.setText(f"RomM unavailable • {message}"))
        QTimer.singleShot(0, verifier.start)

    if selector.exec() != selector.DialogCode.Accepted:
        if verifier is not None and verifier.isRunning():
            verifier.quit()
            verifier.wait(1000)
        return

    window = WorkspaceDashboardWindow(load_config())
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
