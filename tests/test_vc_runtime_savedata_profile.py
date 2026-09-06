from romm_vita_manager.vc_runtime_profiles import (
    build_classic_runtime_profile,
    runtime_guidance_details,
)


def _exheader_with_savedata(size: int) -> bytes:
    exheader = bytearray(0x800)
    exheader[0x1C0:0x1C8] = size.to_bytes(8, "little")
    return bytes(exheader)


def test_classic_profile_records_donor_savedata_size_from_exheader():
    profile = build_classic_runtime_profile(
        "gbc",
        {"title_id": "0004000001234500"},
        code=b"code",
        exheader=_exheader_with_savedata(0x20000),
        romfs_template=b"romfs",
        rom_path="/rom/game.gbc",
    )

    assert profile["save_data_size"] == 0x20000

    config = {"classic_vc": {"gbc": {"runtime_profile": profile}}}
    assert "Donor 3DS SaveData size: 128 KiB (131072 bytes)" in runtime_guidance_details(
        config, "gbc"
    )


def test_short_synthetic_exheader_keeps_savedata_metadata_optional():
    profile = build_classic_runtime_profile(
        "nes",
        {},
        code=b"code",
        exheader=b"short-test-exheader",
        romfs_template=b"romfs",
        rom_path="/rom/game.tnes",
    )

    assert "save_data_size" not in profile
