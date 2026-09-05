import hashlib

import pytest

from romm_vita_manager.vc_runtime_profiles import (
    build_classic_runtime_profile,
    build_gba_runtime_profile,
    classic_runtime_profile_matches,
    configured_runtime_profile,
    gba_runtime_profile_matches,
    guidance_for_family,
)


def test_gba_guidance_accepts_any_genuine_gba_vc_donor():
    guidance = guidance_for_family("gba")
    assert guidance.classification == "recommended"
    assert "AGB_FIRM" in guidance.recommendation
    assert "genuine GBA Virtual Console donor" in guidance.recommendation


def test_gb_guidance_warns_against_special_pokemon_runtime_as_general_donor():
    guidance = guidance_for_family("gb")
    assert guidance.classification == "profile-unverified"
    assert "Pokemon" in guidance.recommendation
    assert "standard late retail" in guidance.recommendation


def test_nes_and_snes_guidance_keep_hardware_limits_explicit():
    nes = guidance_for_family("nes")
    snes = guidance_for_family("snes")
    assert nes.classification == "hardware-retest-required"
    assert "later standard retail" in nes.recommendation
    assert snes.classification == "experimental"
    assert "preset" in snes.recommendation


def test_classic_runtime_profile_is_deterministic_and_sensitive_to_runtime_code():
    kwargs = {
        "family": "nes",
        "donor_info": {"title_id": "0004000001234500"},
        "code": b"runtime-code-a",
        "exheader": b"exheader",
        "romfs_template": b"romfs-template",
        "rom_path": "/rom/game.tnes",
    }
    first = build_classic_runtime_profile(**kwargs)
    second = build_classic_runtime_profile(**kwargs)
    changed = build_classic_runtime_profile(**{**kwargs, "code": b"runtime-code-b"})

    assert first == second
    assert first["profile_id"] != changed["profile_id"]
    assert first["code_sha256"] == hashlib.sha256(b"runtime-code-a").hexdigest()
    assert first["classification"] == "hardware-retest-required"
    assert classic_runtime_profile_matches(
        first,
        "nes",
        code=kwargs["code"],
        exheader=kwargs["exheader"],
        romfs_template=kwargs["romfs_template"],
        rom_path=kwargs["rom_path"],
    )
    assert not classic_runtime_profile_matches(
        first,
        "nes",
        code=b"tampered-runtime",
        exheader=kwargs["exheader"],
        romfs_template=kwargs["romfs_template"],
        rom_path=kwargs["rom_path"],
    )


def test_gba_runtime_profile_records_retail_donor_identity_and_runtime_structure():
    code_hash = hashlib.sha256(b"retail-gba-code").hexdigest()
    profile = build_gba_runtime_profile(
        {"title_id": "0004000000075400"},
        boot_logo=b"logo",
        donor_banner=b"banner",
        donor_icon=b"icon",
        donor_code_sha256=code_hash,
        donor_rom_size=0x200000,
    )
    assert profile["family"] == "gba"
    assert profile["classification"] == "recommended"
    assert profile["donor_title_id"] == "0004000000075400"
    assert profile["donor_code_sha256"] == code_hash
    assert profile["donor_rom_size"] == 0x200000
    assert profile["boot_logo_sha256"] == hashlib.sha256(b"logo").hexdigest()
    assert gba_runtime_profile_matches(
        profile,
        boot_logo=b"logo",
        donor_banner=b"banner",
        donor_icon=b"icon",
    )
    assert not gba_runtime_profile_matches(
        profile,
        boot_logo=b"changed-logo",
        donor_banner=b"banner",
        donor_icon=b"icon",
    )


def test_gba_runtime_profile_rejects_invalid_structural_fingerprint():
    with pytest.raises(ValueError, match="SHA-256"):
        build_gba_runtime_profile(
            {"title_id": "0004000000075400"},
            boot_logo=b"logo",
            donor_banner=b"banner",
            donor_icon=b"icon",
            donor_code_sha256="not-a-hash",
            donor_rom_size=0x200000,
        )


def test_configured_runtime_profile_reads_gba_and_classic_locations():
    gba = {"profile_id": "gba-profile"}
    nes = {"profile_id": "nes-profile"}
    config = {
        "gba_vc": {"runtime_profile": gba},
        "classic_vc": {"nes": {"runtime_profile": nes}},
    }
    assert configured_runtime_profile(config, "gba") == gba
    assert configured_runtime_profile(config, "nes") == nes
    assert configured_runtime_profile(config, "gb") is None


def test_unknown_family_guidance_is_rejected():
    with pytest.raises(ValueError, match="Unsupported Virtual Console donor guidance family"):
        guidance_for_family("genesis")
