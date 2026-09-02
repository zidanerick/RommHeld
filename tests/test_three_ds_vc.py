from pathlib import Path

import pytest

from romm_vita_manager.three_ds_vc import (
    GBA_NATIVE_PROFILE,
    profile_for_rom,
    validate_gba_native_assets,
    validate_native_gba_title_id,
)


def test_gba_profile_matches_supported_extensions():
    assert profile_for_rom("Pokemon.gba") == GBA_NATIVE_PROFILE
    assert profile_for_rom("Pokemon.AGB") == GBA_NATIVE_PROFILE
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
