from __future__ import annotations

from pathlib import Path

from romm_vita_manager import platform_services as platform_services_module
from romm_vita_manager.platform_services import (
    cache_dir,
    config_dir,
    config_path,
    is_web_url,
    open_external_url,
    temp_dir,
    volume_info,
)


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


def test_web_url_validation_accepts_only_complete_http_urls():
    assert is_web_url("https://example.com/path")
    assert is_web_url("http://example.com")
    assert is_web_url("  https://example.com/releases  ")
    assert not is_web_url("ftp://example.com")
    assert not is_web_url("example.com")
    assert not is_web_url("https:///missing-host")


def test_external_url_uses_qt_desktop_service(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(
        platform_services_module,
        "_desktop_open_url",
        lambda url: opened.append(url.toString()) or True,
    )

    assert open_external_url("https://example.com/releases")
    assert opened == ["https://example.com/releases"]


def test_external_url_reports_invalid_and_desktop_service_failure(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(
        platform_services_module,
        "_desktop_open_url",
        lambda url: opened.append(url.toString()) or False,
    )

    assert not open_external_url("not a URL")
    assert opened == []
    assert not open_external_url("https://example.com")
    assert opened == ["https://example.com"]
