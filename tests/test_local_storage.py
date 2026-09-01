from pathlib import Path

import pytest

from romm_vita_manager.local_storage import resolve_destination, resolve_storage_root, storage_summary


def test_resolve_storage_root_requires_existing_directory(tmp_path: Path):
    assert resolve_storage_root(tmp_path) == tmp_path.resolve()
    with pytest.raises(ValueError):
        resolve_storage_root(tmp_path / "missing")


def test_resolve_destination_stays_inside_root(tmp_path: Path):
    root = tmp_path / "sd"
    root.mkdir()
    assert resolve_destination(root, "roms/gba/game.gba") == (root / "roms/gba/game.gba").resolve()
    with pytest.raises(ValueError):
        resolve_destination(root, "../outside.bin")
    with pytest.raises(ValueError):
        resolve_destination(root, "/../outside.bin")


def test_storage_summary_reports_host_filesystem_space(tmp_path: Path):
    total, free = storage_summary(tmp_path)
    assert total is not None
    assert free is not None
    assert total >= free >= 0
