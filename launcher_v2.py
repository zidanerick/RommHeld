#!/usr/bin/env python3
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from romm_vita_manager.config import load_config
from romm_vita_manager.console_selector import PlatformSelectorDialog
from romm_vita_manager.workspace_dashboard import WorkspaceDashboardWindow


def main() -> None:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("RommHeld")
    app.setApplicationVersion("1.0")
    selector = PlatformSelectorDialog(load_config())
    if selector.exec() != selector.DialogCode.Accepted:
        return
    window = WorkspaceDashboardWindow(load_config())
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
