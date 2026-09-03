import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from romm_vita_manager.workspace_dashboard import WorkspaceDashboardWindow


def test_workspace_constructs_without_legacy_main_window(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    config = {
        "active_console": "vita",
        "setup_complete": True,
        "library_source": {
            "mode": "local",
            "local_root": str(tmp_path),
            "romm_url": "",
            "api_token": "",
        },
        "platform_mappings": {},
        "devices": {},
    }
    window = WorkspaceDashboardWindow(config)
    try:
        assert window.centralWidget() is window.shell
        assert window.local_library.parent() is not None
    finally:
        window.close()
        app.processEvents()
