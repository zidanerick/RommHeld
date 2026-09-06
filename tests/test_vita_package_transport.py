from __future__ import annotations

import threading
from pathlib import Path

import pytest

from romm_vita_manager.package_manager import PackageSpec
from romm_vita_manager.vita_ftp import VitaFtpSettings
from romm_vita_manager.vita_package_transport import (
    package_ftp_destination,
    stage_package_via_ftp,
)


def package(*, destination: str = "root", archive: bool = False) -> PackageSpec:
    return PackageSpec(
        key="test",
        name="Test package",
        description="test",
        source="direct:https://example.invalid/test.vpk",
        asset_name="test.vpk",
        stage_name="test.vpk",
        destination=destination,
        requires_archive_review=archive,
    )


def test_package_ftp_destination_matches_local_staging_layout():
    assert package_ftp_destination(package()) == "test.vpk"
    assert package_ftp_destination(package(destination="runtime")) == "data/runtime/test.vpk"


def test_archive_package_is_not_staged_over_ftp():
    with pytest.raises(RuntimeError, match="archive package"):
        package_ftp_destination(package(archive=True))


def test_stage_package_via_ftp_uses_safe_overwrite_and_reports_ux0_path(monkeypatch, tmp_path: Path):
    source = tmp_path / "test.vpk"
    source.write_bytes(b"package")
    monkeypatch.setattr("romm_vita_manager.vita_package_transport.package_path", lambda _package: source)

    calls = {}

    class FakeBackend:
        def __init__(self, settings):
            calls["settings"] = settings

        def connect(self):
            calls["connected"] = True

        def upload(self, local_path, destination, **kwargs):
            calls["local_path"] = local_path
            calls["destination"] = destination
            calls["kwargs"] = kwargs
            return "copied", local_path.stat().st_size

        def close(self):
            calls["closed"] = True

    cancel = threading.Event()
    result, target = stage_package_via_ftp(
        package(destination="runtime"),
        VitaFtpSettings(host="192.0.2.20"),
        cancel_event=cancel,
        progress=lambda _done: None,
        backend_factory=FakeBackend,
    )

    assert result == "copied"
    assert target == "ux0:/data/runtime/test.vpk"
    assert calls["destination"] == "data/runtime/test.vpk"
    assert calls["kwargs"]["overwrite"] is True
    assert calls["kwargs"]["cancel_event"] is cancel
    assert calls["connected"] and calls["closed"]


def test_stage_package_via_ftp_requires_cached_package(monkeypatch, tmp_path: Path):
    missing = tmp_path / "missing.vpk"
    monkeypatch.setattr("romm_vita_manager.vita_package_transport.package_path", lambda _package: missing)

    with pytest.raises(FileNotFoundError, match="has not been downloaded"):
        stage_package_via_ftp(
            package(),
            VitaFtpSettings(host="192.0.2.20"),
            backend_factory=lambda _settings: None,
        )
