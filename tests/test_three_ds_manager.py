from __future__ import annotations

import ast
from pathlib import Path

from romm_vita_manager.three_ds_paths import default_3ds_destination


def test_default_3ds_destination_for_nds():
    assert default_3ds_destination("Mario.nds", ".nds") == "/roms/nds/Mario.nds"


def test_default_3ds_destination_for_gba():
    assert default_3ds_destination("Metroid.gba", ".gba") == "/roms/gba/Metroid.gba"


def test_default_3ds_destination_leaves_other_formats_explicit():
    assert default_3ds_destination("Homebrew.3dsx", ".3dsx") == "Homebrew.3dsx"
    assert default_3ds_destination("Title.cia", ".cia") == "Title.cia"


def test_manager_uses_shared_runtime_preference_policy_without_importing_qt():
    source_path = Path(__file__).parents[1] / "romm_vita_manager" / "three_ds_manager.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "get_device_preference" in imported_names
    assert "preferred_target_key" in imported_names
    assert "get_device_preference" in called_names
    assert "preferred_target_key" in called_names
    assert '"native_gba" if game.platform_slug == "gba" else "retroarch"' not in source
