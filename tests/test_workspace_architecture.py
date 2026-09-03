from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "romm_vita_manager"
LEGACY_MODULES = {"app", "ui", "platform_selector"}


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


def _legacy_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            leaf = module.rsplit(".", 1)[-1]
            if leaf in LEGACY_MODULES:
                found.append(module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                leaf = alias.name.rsplit(".", 1)[-1]
                if leaf in LEGACY_MODULES:
                    found.append(alias.name)
    return found


def test_workspace_is_a_direct_main_window() -> None:
    path = PACKAGE / "workspace_dashboard.py"
    assert _class_bases(path, "WorkspaceDashboardWindow") == ["QMainWindow"]


def test_local_library_is_not_a_legacy_main_window() -> None:
    path = PACKAGE / "local_library.py"
    assert _class_bases(path, "LocalLibraryWidget") == ["QWidget"]


def test_workspace_does_not_import_legacy_main_window() -> None:
    source = (PACKAGE / "workspace_dashboard.py").read_text(encoding="utf-8")
    assert "BaseMainWindow" not in source
    assert "MainWindow as" not in source


def test_removed_legacy_modules_have_no_callers() -> None:
    offenders: dict[str, list[str]] = {}
    for path in sorted(PACKAGE.glob("*.py")):
        if path.stem in LEGACY_MODULES:
            continue
        imports = _legacy_imports(path)
        if imports:
            offenders[path.name] = imports
    assert offenders == {}


def test_legacy_module_files_are_removed() -> None:
    for module in LEGACY_MODULES:
        assert not (PACKAGE / f"{module}.py").exists()


def test_compatibility_script_uses_current_launcher() -> None:
    source = (ROOT / "romm_vita_manager.py").read_text(encoding="utf-8")
    assert "from launcher import main" in source
    assert "romm_vita_manager.ui" not in source
