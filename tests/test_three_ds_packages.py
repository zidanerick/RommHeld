from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from romm_vita_manager.three_ds_packages import (
    BACKUP_SUFFIX,
    ResolvedThreeDSPackage,
    get_package,
    package_for_app,
    resolve_package,
    stage_package,
)


def _high_confidence_3ds_root(root: Path) -> None:
    (root / "boot.firm").write_bytes(b"firm")
    (root / "boot.3dsx").write_bytes(b"3dsx")
    (root / "luma").mkdir()


def test_only_simple_auditable_apps_have_direct_staging_packages():
    assert package_for_app("ftpd").asset_name == "ftpd.3dsx"
    assert package_for_app("universal-updater").asset_name == "Universal-Updater.3dsx"
    assert package_for_app("red-viper").asset_name == "red-viper.3dsx"
    assert package_for_app("twilight") is None
    assert package_for_app("retroarch") is None
    assert package_for_app("daedalusx64") is None
    assert package_for_app("luma") is None


def test_resolve_package_requires_exact_official_release_asset(monkeypatch):
    digest = "a" * 64
    monkeypatch.setattr(
        "romm_vita_manager.three_ds_packages._request_json",
        lambda url: {
            "tag_name": "v1.2.3",
            "draft": False,
            "prerelease": False,
            "assets": [
                {
                    "name": "ftpd.3dsx",
                    "browser_download_url": "https://github.com/mtheall/ftpd/releases/download/v1.2.3/ftpd.3dsx",
                    "size": 1234,
                    "digest": f"sha256:{digest}",
                }
            ],
        },
    )

    resolved = resolve_package(get_package("ftpd-3dsx"))

    assert resolved.version == "v1.2.3"
    assert resolved.size == 1234
    assert resolved.sha256 == digest


def test_resolve_package_rejects_unexpected_download_host(monkeypatch):
    monkeypatch.setattr(
        "romm_vita_manager.three_ds_packages._request_json",
        lambda url: {
            "tag_name": "v1",
            "assets": [
                {
                    "name": "ftpd.3dsx",
                    "browser_download_url": "https://example.invalid/ftpd.3dsx",
                    "size": 1234,
                }
            ],
        },
    )

    with pytest.raises(RuntimeError, match="Unexpected download host"):
        resolve_package(get_package("ftpd-3dsx"))


def test_stage_package_requires_high_confidence_3ds_root(tmp_path: Path):
    source = tmp_path / "package.3dsx"
    source.write_bytes(b"package")
    spec = get_package("ftpd-3dsx")
    resolved = ResolvedThreeDSPackage(
        spec,
        "v1",
        "https://github.com/example/example/releases/download/v1/package.3dsx",
        source.stat().st_size,
        hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    sd_root = tmp_path / "sd"
    sd_root.mkdir()

    with pytest.raises(ValueError, match="high-confidence"):
        stage_package(resolved, source, sd_root)


def test_stage_package_backs_up_existing_file_and_replaces_atomically(tmp_path: Path):
    sd_root = tmp_path / "sd"
    sd_root.mkdir()
    _high_confidence_3ds_root(sd_root)

    spec = get_package("red-viper-3dsx")
    target = sd_root / spec.destination
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old-version")

    source = tmp_path / "red-viper.3dsx"
    source.write_bytes(b"new-version")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    resolved = ResolvedThreeDSPackage(
        spec,
        "v1.3.2",
        "https://github.com/skyfloogle/red-viper/releases/download/v1.3.2/red-viper.3dsx",
        source.stat().st_size,
        digest,
    )

    result = stage_package(resolved, source, sd_root)

    assert result == target
    assert target.read_bytes() == b"new-version"
    assert target.with_name(target.name + BACKUP_SUFFIX).read_bytes() == b"old-version"
    assert not target.with_name(target.name + ".rommheld.tmp").exists()


def test_stage_package_reverifies_cached_digest(tmp_path: Path):
    sd_root = tmp_path / "sd"
    sd_root.mkdir()
    _high_confidence_3ds_root(sd_root)
    source = tmp_path / "ftpd.3dsx"
    source.write_bytes(b"tampered")
    spec = get_package("ftpd-3dsx")
    resolved = ResolvedThreeDSPackage(
        spec,
        "v3.2.1",
        "https://github.com/mtheall/ftpd/releases/download/v3.2.1/ftpd.3dsx",
        source.stat().st_size,
        "0" * 64,
    )

    with pytest.raises(IOError, match="failed SHA-256"):
        stage_package(resolved, source, sd_root)
