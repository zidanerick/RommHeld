from pathlib import Path

import pytest

from romm_vita_manager.vita_paths import vita_target


def test_vita_target_maps_ux0_to_mount_root(tmp_path: Path):
    assert vita_target(tmp_path, "ux0:/data/file.zip") == (tmp_path / "data" / "file.zip").resolve()


def test_vita_target_accepts_ux0_root(tmp_path: Path):
    assert vita_target(tmp_path, "ux0:/") == tmp_path.resolve()
    assert vita_target(tmp_path, "ux0:") == tmp_path.resolve()
    assert vita_target(tmp_path, "ux0") == tmp_path.resolve()


def test_vita_target_rejects_traversal(tmp_path: Path):
    with pytest.raises(ValueError, match="remain inside"):
        vita_target(tmp_path, "ux0:/../outside.bin")


def test_vita_target_rejects_other_vita_volumes(tmp_path: Path):
    with pytest.raises(ValueError, match="must use"):
        vita_target(tmp_path, "uma0:/data/file.bin")