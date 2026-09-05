from pathlib import Path

from romm_vita_manager.three_ds_runtime_details import (
    RETROARCH_CORE_PROFILES,
    scan_retroarch_route,
    scan_twilight_runtime,
)


def _retroarch_root(root: Path, config: str = "") -> Path:
    retroarch = root / "RetroArch"
    (retroarch / "Cores").mkdir(parents=True)
    if config:
        (retroarch / "retroarch.cfg").write_text(config, encoding="utf-8")
    return retroarch


def test_twilight_runtime_requires_frontend_assets_and_nds_bootstrap(tmp_path: Path):
    (tmp_path / "BOOT.NDS").write_bytes(b"launcher")
    assert scan_twilight_runtime(tmp_path).state == "incomplete"

    twilight = tmp_path / "_nds" / "TWiLightMenu"
    twilight.mkdir(parents=True)
    assert scan_twilight_runtime(tmp_path).state == "incomplete"

    (tmp_path / "_nds" / "nds-bootstrap").mkdir()
    status = scan_twilight_runtime(tmp_path)
    assert status.state == "ready"
    assert status.twilight_assets
    assert status.nds_bootstrap
    assert status.boot_nds


def test_retroarch_cia_is_installer_evidence_not_installed_title_proof(tmp_path: Path):
    retroarch = _retroarch_root(tmp_path)
    (retroarch / "Cores" / "mgba_libretro.cia").write_bytes(b"cia")

    status = scan_retroarch_route(tmp_path, "gba")

    assert status.state == "core_installer_evidence"
    assert [path.name for path in status.active_core_files] == ["mgba_libretro.cia"]
    assert "Confirm on the console" in status.note


def test_retroarch_3dsx_core_is_launchable_sd_evidence(tmp_path: Path):
    retroarch = _retroarch_root(tmp_path)
    (retroarch / "Cores" / "GAMBATTE_LIBRETRO.3DSX").write_bytes(b"3dsx")

    status = scan_retroarch_route(tmp_path, "gbc")

    assert status.state == "launchable_sd_core_detected"
    assert status.profile is not None
    assert status.profile.retroachievements_recommended


def test_retroarch_core_in_notused_directory_is_not_called_active(tmp_path: Path):
    retroarch = _retroarch_root(tmp_path)
    inactive = retroarch / "Cores-Notused"
    inactive.mkdir()
    (inactive / "fceumm_libretro.cia").write_bytes(b"cia")

    status = scan_retroarch_route(tmp_path, "nes")

    assert status.state == "core_staged_inactive"
    assert not status.active_core_files
    assert status.inactive_core_files


def test_fds_firmware_is_checked_only_when_system_directory_is_explicit(tmp_path: Path):
    retroarch = _retroarch_root(tmp_path)
    (retroarch / "Cores" / "fceumm_libretro.3dsx").write_bytes(b"3dsx")

    unknown = scan_retroarch_route(tmp_path, "fds")
    assert unknown.state == "firmware_unverified"
    assert unknown.system_directory is None

    (retroarch / "retroarch.cfg").write_text(
        'system_directory = "sdmc:/RetroArch/system"\n',
        encoding="utf-8",
    )
    (retroarch / "system").mkdir()
    missing = scan_retroarch_route(tmp_path, "fds")
    assert missing.state == "missing_firmware"
    assert missing.missing_firmware[0].key == "fds-bios"

    (retroarch / "system" / "DISKSYS.ROM").write_bytes(b"bios")
    ready = scan_retroarch_route(tmp_path, "fds")
    assert ready.state == "launchable_sd_core_detected"
    assert ready.found_firmware == ("disksys.rom",)


def test_segacd_requires_at_least_one_region_bios_in_explicit_system_directory(tmp_path: Path):
    retroarch = _retroarch_root(
        tmp_path,
        'system_directory = "sdmc:/RetroArch/system"\n',
    )
    (retroarch / "Cores" / "genesis_plus_gx_libretro.3dsx").write_bytes(b"3dsx")
    (retroarch / "system").mkdir()

    missing = scan_retroarch_route(tmp_path, "segacd")
    assert missing.state == "missing_firmware"

    (retroarch / "system" / "bios_CD_U.bin").write_bytes(b"bios")
    found = scan_retroarch_route(tmp_path, "segacd")
    assert found.state == "launchable_sd_core_detected"
    assert found.found_firmware == ("bios_CD_U.bin",)


def test_snes_profile_exists_but_is_not_retroachievements_recommended():
    profile = RETROARCH_CORE_PROFILES["snes"]
    assert profile.core_ids == (
        "snes9x2002",
        "snes9x2005",
        "snes9x2005_plus",
        "snes9x2010",
    )
    assert not profile.retroachievements_recommended
