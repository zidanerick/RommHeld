#!/usr/bin/env python3
"""RommHeld application launcher."""
from __future__ import annotations

from romm_vita_manager.config import load_config
from romm_vita_manager.device_dashboard import DeviceDashboardWindow
from romm_vita_manager.platform_selector import PlatformSelectorDialog


def main() -> None:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("RommHeld")
    app.setApplicationVersion("1.0")

    config = load_config()
    selector = PlatformSelectorDialog(config)
    if selector.exec() != selector.DialogCode.Accepted:
        return

    config = load_config()
    window = DeviceDashboardWindow(config)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
