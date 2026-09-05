import hashlib
import io
import zipfile

from romm_vita_manager.classic_vc import (
    _patch_exheader,
    build_romfs,
    classic_title_id_for_romm_id,
    parse_romfs_files,
    prepare_classic_rom,
)


def _valid_gameboy_rom(*, cgb_flag: int = 0x00) -> bytes:
    data = bytearray(0x8000)
    data[0x134:0x13C] = b"ROMMHELD"
    data[0x143] = cgb_flag
    data[0x147] = 0x00
    data[0x148] = 0x00
    data[0x149] = 0x00
    checksum = 0
    for value in data[0x134:0x14D]:
        checksum = (checksum - value - 1) & 0xFF
    data[0x14D] = checksum
    return bytes(data)


def test_classic_title_ids_are_stable_and_family_specific():
    gb = classic_title_id_for_romm_id(42, "gb")
    gbc = classic_title_id_for_romm_id(42, "gbc")
    assert len(gb) == 8
    assert gb.hex().startswith("00040000")
    assert gb == classic_title_id_for_romm_id(42, "gb")
    assert gb != classic_title_id_for_romm_id(43, "gb")
    assert gb != gbc


def test_nested_romfs_round_trip_preserves_paths_and_empty_placeholder():
    files = {
        "/config.ini": b"mode=vc\n",
        "/lang/EU-English.lang": b"english",
        "/rom/DMGTEST0.000": b"",
        "/snd/effect.bcsar": b"audio",
    }
    rebuilt = build_romfs(files)
    assert rebuilt.startswith(b"IVFC")
    assert parse_romfs_files(rebuilt) == files


def test_romfs_uses_retail_physical_level3_layout_and_padded_hashes():
    files = {
        "/config.ini": b"mode=vc\n",
        "/rom/DMGTEST0.000": b"ROM" * 1733,
    }
    rebuilt = build_romfs(files)
    block = 0x1000

    # Retail 3DS RomFS places the Level-3 filesystem at physical 0x1000;
    # the offsets in the IVFC descriptors are logical hash-tree offsets.
    assert int.from_bytes(rebuilt[0x1000:0x1004], "little") == 0x28

    master_size = int.from_bytes(rebuilt[0x08:0x0C], "little")
    level1_size = int.from_bytes(rebuilt[0x14:0x1C], "little")
    level2_size = int.from_bytes(rebuilt[0x2C:0x34], "little")
    level3_size = int.from_bytes(rebuilt[0x44:0x4C], "little")

    level3_physical = 0x1000
    level1_physical = level3_physical + ((level3_size + block - 1) // block) * block
    level2_physical = level1_physical + ((level1_size + block - 1) // block) * block

    level3 = rebuilt[level3_physical : level3_physical + level3_size]
    level2 = rebuilt[level2_physical : level2_physical + level2_size]
    level1 = rebuilt[level1_physical : level1_physical + level1_size]
    master = rebuilt[0x60 : 0x60 + master_size]

    def hashes(data: bytes) -> bytes:
        return b"".join(
            hashlib.sha256(data[offset : offset + block].ljust(block, b"\x00")).digest()
            for offset in range(0, len(data), block)
        )

    assert hashes(level3) == level2
    assert hashes(level2) == level1
    assert hashes(level1) == master


def test_patch_exheader_updates_identity_without_touching_access_descriptor():
    donor = bytes((index * 17) & 0xFF for index in range(0x800))
    title_id = classic_title_id_for_romm_id(7, "gb")
    patched = _patch_exheader(donor, title_id, "CTR-N-RHGB")
    assert patched[0x1C8:0x1D0] == title_id[::-1]
    assert patched[0x200:0x208] == title_id[::-1]
    assert patched[0x400:] == donor[0x400:]
    assert patched != donor


def test_prepare_classic_rom_accepts_raw_rom():
    rom = _valid_gameboy_rom()
    assert prepare_classic_rom(rom, "gb") == rom


def test_prepare_classic_rom_extracts_matching_file_from_zip():
    expected = _valid_gameboy_rom(cgb_flag=0x80)
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("readme.txt", "notes")
        archive.writestr("games/Oracle.gbc", expected)
    assert prepare_classic_rom(archive_bytes.getvalue(), "gbc") == expected


def test_prepare_classic_rom_rejects_wrong_zip_family():
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("game.nes", b"NES")
    try:
        prepare_classic_rom(archive_bytes.getvalue(), "gb")
    except ValueError as exc:
        assert "does not contain" in str(exc)
    else:
        raise AssertionError("Expected ZIP without a Game Boy ROM to be rejected")
