from __future__ import annotations

from pathlib import Path

import pytest

import romm_vita_manager.classic_vc_assets as assets
from romm_vita_manager.vc_runtime_profiles import build_classic_runtime_profile


def _cache_config(tmp_path: Path, family: str, version: int, *, ncch_logo: bool = False) -> dict:
    paths = {}
    for key, filename, data in (
        ("exheader_path", "exheader.bin", b"E"),
        ("code_path", "code.bin", b"C"),
        ("romfs_template_path", "romfs.bin", b"R"),
        ("donor_banner_path", "banner.bin", b"B"),
        ("donor_icon_path", "icon.smdh", b"I"),
    ):
        path = tmp_path / f"{family}-{filename}"
        path.write_bytes(data)
        paths[key] = str(path)
    entry = {
        "cache_version": version,
        **paths,
        "logo_path": "",
        "rom_path": "/rom/game.bin" if family != "snes" else "/data.bin",
        "ncch_plain_path": "",
        "ncch_logo_path": "",
    }
    if ncch_logo:
        path = tmp_path / f"{family}-ncch-logo.bin"
        path.write_bytes(b"L" * 0x2000)
        entry["ncch_logo_path"] = str(path)
    return {"classic_vc": {family: entry}}


def test_v4_gbc_cache_remains_usable_without_forcing_working_family_reprepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(assets, "validate_retail_romfs", lambda data: None)
    config = _cache_config(tmp_path, "gbc", 4)
    assert assets.configured_classic_runtime(config, "gbc") is not None


def test_v4_nes_cache_is_rejected_because_it_lacks_retail_ncch_launch_logo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(assets, "validate_retail_romfs", lambda data: None)
    config = _cache_config(tmp_path, "nes", 4)
    assert assets.configured_classic_runtime(config, "nes") is None


def test_v5_nes_cache_requires_real_sized_dedicated_logo_region(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(assets, "validate_retail_romfs", lambda data: None)
    missing = _cache_config(tmp_path, "nes", 5)
    assert assets.configured_classic_runtime(missing, "nes") is None

    complete = _cache_config(tmp_path, "nes", 5, ncch_logo=True)
    paths = assets.configured_classic_runtime(complete, "nes")
    assert paths is not None
    assert paths.ncch_logo is not None
    assert paths.ncch_logo.stat().st_size == 0x2000


def test_profiled_classic_cache_is_rejected_after_runtime_file_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(assets, "validate_retail_romfs", lambda data: None)
    config = _cache_config(tmp_path, "gbc", 5)
    entry = config["classic_vc"]["gbc"]
    entry["runtime_profile"] = build_classic_runtime_profile(
        "gbc",
        {"title_id": "0004000001234500"},
        code=b"C",
        exheader=b"E",
        romfs_template=b"R",
        rom_path=entry["rom_path"],
    )
    assert assets.configured_classic_runtime(config, "gbc") is not None

    Path(entry["code_path"]).write_bytes(b"tampered")
    assert assets.configured_classic_runtime(config, "gbc") is None
