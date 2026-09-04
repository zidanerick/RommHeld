from pathlib import Path

from romm_vita_manager.gba_assets import (
    cached_boot_logo_path,
    cached_donor_icon_path,
    configured_boot_logo,
    configured_donor_banner,
    configured_donor_icon,
)


def test_configured_boot_logo_missing_returns_none(tmp_path):
    config = {"gba_vc": {"boot_logo_path": str(tmp_path / "missing.bin")}}
    assert configured_boot_logo(config) is None


def test_cached_boot_logo_path_is_package_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "romm_vita_manager.gba_assets.package_cache_dir",
        lambda: tmp_path,
    )
    assert cached_boot_logo_path() == Path(tmp_path) / "agb_firm_boot_logo.bin"
    assert cached_donor_icon_path() == Path(tmp_path) / "gba_vc_donor_icon.smdh"


def test_old_gba_banner_cache_without_icon_is_stale(tmp_path):
    banner = tmp_path / "banner.bin"
    banner.write_bytes(b"banner")
    config = {"gba_vc": {"donor_banner_path": str(banner)}}
    assert configured_donor_banner(config) is None


def test_gba_presentation_cache_requires_banner_and_icon(tmp_path):
    banner = tmp_path / "banner.bin"
    icon = tmp_path / "icon.smdh"
    banner.write_bytes(b"banner")
    icon.write_bytes(b"icon")
    config = {
        "gba_vc": {
            "donor_banner_path": str(banner),
            "donor_icon_path": str(icon),
        }
    }
    assert configured_donor_banner(config) == banner
    assert configured_donor_icon(config) == icon
