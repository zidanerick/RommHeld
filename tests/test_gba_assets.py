from pathlib import Path

from romm_vita_manager.gba_assets import configured_boot_logo, cached_boot_logo_path


def test_configured_boot_logo_missing_returns_none(tmp_path):
    config = {"gba_vc": {"boot_logo_path": str(tmp_path / "missing.bin")}}
    assert configured_boot_logo(config) is None


def test_cached_boot_logo_path_is_package_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "romm_vita_manager.gba_assets.package_cache_dir",
        lambda: tmp_path,
    )
    assert cached_boot_logo_path() == Path(tmp_path) / "agb_firm_boot_logo.bin"
