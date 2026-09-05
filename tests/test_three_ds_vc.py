from pathlib import Path

import pytest

from romm_vita_manager.three_ds_vc import (
    GAME_GEAR_PROFILE,
    GBA_NATIVE_PROFILE,
    GBC_PROFILE,
    GB_PROFILE,
    NES_PROFILE,
    SNES_PROFILE,
    profile_for_platform,
    profile_for_rom,
    validate_gba_native_assets,
    validate_native_gba_title_id,
)


def test_vc_profiles_match_nintendo_platform_families():
    assert profile_for_platform("gb") == GB_PROFILE
    assert profile_for_platform("gbc") == GBC_PROFILE
    assert profile_for_platform("gba") == GBA_NATIVE_PROFILE
    assert profile_for_platform("nes") == NES_PROFILE
    assert profile_for_platform("famicom") is None
    assert profile_for_platform("fds") is None
    assert profile_for_platform("snes") == SNES_PROFILE
    assert profile_for_platform("gamegear") == GAME_GEAR_PROFILE
    assert profile_for_platform("genesis") is None


def test_all_supported_nintendo_vc_injectors_are_marked_implemented():
    assert GBA_NATIVE_PROFILE.implemented
    assert GB_PROFILE.implemented
    assert GBC_PROFILE.implemented
    assert NES_PROFILE.implemented
    assert SNES_PROFILE.implemented
    assert GAME_GEAR_PROFILE.implemented
    assert SNES_PROFILE.requires_new_3ds


def test_rom_extension_detection_is_advisory():
    assert profile_for_rom("Pokemon.gba") == GBA_NATIVE_PROFILE
    assert profile_for_rom("Pokemon.AGB") == GBA_NATIVE_PROFILE
    assert profile_for_rom("Zelda.gbc") == GBC_PROFILE
    assert profile_for_rom("Metroid.nes") == NES_PROFILE
    assert profile_for_rom("Mario.sfc") == SNES_PROFILE
    assert profile_for_rom("Sonic.gg") == GAME_GEAR_PROFILE
    assert profile_for_rom("Pokemon.nds") is None


def test_native_gba_title_id_is_constrained_to_agb_firm_range():
    assert validate_native_gba_title_id("0004000000F12300") == "0004000000f12300"
    with pytest.raises(ValueError):
        validate_native_gba_title_id("0004000012345678")
    with pytest.raises(ValueError):
        validate_native_gba_title_id("not-a-title-id")


def test_native_gba_assets_must_exist(tmp_path: Path):
    boot_logo = tmp_path / "logo.bin"
    boot9 = tmp_path / "boot9.bin"
    boot_logo.write_bytes(b"logo")
    boot9.write_bytes(b"boot9")

    validate_gba_native_assets(boot_logo=boot_logo, boot9=boot9)

    with pytest.raises(FileNotFoundError):
        validate_gba_native_assets(boot_logo=boot_logo, boot9=tmp_path / "missing.bin")
