from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _class_bases(path: Path, class_name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            result: list[str] = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    result.append(base.id)
                elif isinstance(base, ast.Attribute):
                    result.append(base.attr)
            return result
    raise AssertionError(f"Class {class_name} not found in {path}")


def test_workspace_is_a_direct_main_window() -> None:
    path = ROOT / "romm_vita_manager" / "workspace_dashboard.py"
    assert _class_bases(path, "WorkspaceDashboardWindow") == ["QMainWindow"]


def test_local_library_is_not_a_legacy_main_window() -> None:
    path = ROOT / "romm_vita_manager" / "local_library.py"
    assert _class_bases(path, "LocalLibraryWidget") == ["QWidget"]


def test_workspace_does_not_import_legacy_main_window() -> None:
    source = (ROOT / "romm_vita_manager" / "workspace_dashboard.py").read_text(
        encoding="utf-8"
    )
    assert "BaseMainWindow" not in source
    assert "MainWindow as" not in source
