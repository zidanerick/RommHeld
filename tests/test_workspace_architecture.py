from PySide6.QtWidgets import QMainWindow

from romm_vita_manager.local_library import LocalLibraryWidget
from romm_vita_manager.workspace_dashboard import WorkspaceDashboardWindow


def test_workspace_is_a_direct_main_window() -> None:
    assert WorkspaceDashboardWindow.__bases__ == (QMainWindow,)


def test_local_library_is_extracted_from_legacy_main_window() -> None:
    names = {base.__name__ for base in LocalLibraryWidget.__mro__}
    assert "MainWindow" not in names
