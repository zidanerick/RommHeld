from pathlib import Path

from romm_vita_manager.three_ds_runtime_details import (
    RETROARCH_CORE_PROFILES,
    scan_retroarch_route,
)
from romm_vita_manager.three_ds_targets import (
    RETROARCH_TARGET_PLATFORM_SLUGS,
    available_targets,
    compatible_platform,
)


def _target_keys(slug: str) -> set[str]:
    return {target.key for target in available_targets(slug)}


def _retroarch_root(root: Path, config: str = "") -> Path:
    retroarch = root / "RetroArch"
    (retroarch / "Cores").mkdir(parents=True)
    if config:
        (retroarch / "retroarch.cfg").write_text(config, encoding="utf-8")
    return retroarch


def test_every_exposed_retroarch_platform_has_an_audited_3ds_core_profile():
    assert set(RETROARCH_CORE_PROFILES) == set(RETROARCH_TARGET_PLATFORM_SLUGS)


def test_stale_generic_routes_are_not_advertised_on_3ds():
    assert "amiga" not in RETROARCH_TARGET_PLATFORM_SLUGS
    assert "scummvm" not in RETROARCH_TARGET_PLATFORM_SLUGS
    assert "retroarch" not in _target_keys("amiga")
    assert "retroarch" not in _target_keys("scummvm")


def test_native_3ds_cia_route_remains_independent_from_retroarch():
    assert "3ds" not in RETROARCH_TARGET_PLATFORM_SLUGS
    assert compatible_platform("3ds")
    assert _target_keys("3ds") == {"native_3ds_cia"}


def test_new_current_recipe_profiles_detect_representative_3dsx_cores(tmp_path: Path):
    retroarch = _retroarch_root(tmp_path)
    examples = {
        "msx": "bluemsx_libretro.3dsx",
        "lynx": "handy_libretro.3dsx",
        "vectrex": "vecx_libretro.3dsx",
        "c64": "vice_x64_libretro.3dsx",
        "dos": "dosbox_svn_libretro.3dsx",
        "wonderswan-color": "mednafen_wswan_libretro.3dsx",
        "neogeomvs": "fbalpha2012_neogeo_libretro.3dsx",
        "neo-geo-pocket-color": "mednafen_ngp_libretro.3dsx",
        "zxs": "fuse_libretro.3dsx",
    }

    for platform_slug, filename in examples.items():
        core = retroarch / "Cores" / filename
        core.write_bytes(b"core")
        status = scan_retroarch_route(tmp_path, platform_slug)
        assert status.state == "launchable_sd_core_detected"
        assert core in status.active_core_files
        core.unlink()


def test_atari_5200_profile_requires_bios_when_system_directory_is_explicit(tmp_path: Path):
    retroarch = _retroarch_root(
        tmp_path,
        'system_directory = "sdmc:/RetroArch/system"\n',
    )
    (retroarch / "Cores" / "atari800_libretro.3dsx").write_bytes(b"core")
    (retroarch / "system").mkdir()

    missing = scan_retroarch_route(tmp_path, "atari5200")
    assert missing.state == "missing_firmware"
    assert missing.missing_firmware[0].key == "atari-5200-bios"

    (retroarch / "system" / "5200.ROM").write_bytes(b"bios")
    ready = scan_retroarch_route(tmp_path, "atari5200")
    assert ready.state == "launchable_sd_core_detected"


def test_turbografx_cd_profile_accepts_a_system_card_bios(tmp_path: Path):
    retroarch = _retroarch_root(
        tmp_path,
        'system_directory = "sdmc:/RetroArch/system"\n',
    )
    (retroarch / "Cores" / "mednafen_pce_fast_libretro.3dsx").write_bytes(b"core")
    (retroarch / "system").mkdir()

    missing = scan_retroarch_route(tmp_path, "turbografx-cd")
    assert missing.state == "missing_firmware"

    (retroarch / "system" / "SYSCARD3.PCE").write_bytes(b"bios")
    ready = scan_retroarch_route(tmp_path, "turbografx-cd")
    assert ready.state == "launchable_sd_core_detected"
    assert ready.found_firmware == ("syscard3.pce",)
