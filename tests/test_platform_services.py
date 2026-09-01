from __future__ import annotations

from pathlib import Path

from romm_vita_manager.platform_services import cache_dir, config_dir, config_path, temp_dir, volume_info


def test_platform_paths_are_absolute():
    assert config_dir().is_absolute()
    assert cache_dir().is_absolute()
    assert config_path().is_absolute()
    assert temp_dir().is_absolute()


def test_config_path_is_in_config_directory():
    assert config_path().parent == config_dir()
    assert config_path().name == "config.json"


def test_volume_info_reports_local_filesystem(tmp_path: Path):
    info = volume_info(tmp_path)
    assert Path(info["root"]).exists()
    assert isinstance(info["filesystem"], str)
    assert isinstance(info["bytes_total"], int)
    assert isinstance(info["bytes_free"], int)
