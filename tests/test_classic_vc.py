import io
import zipfile

from romm_vita_manager.classic_vc import (
    _patch_exheader,
    build_romfs,
    classic_title_id_for_romm_id,
    parse_romfs_files,
    prepare_classic_rom,
)


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


def test_patch_exheader_updates_identity_without_touching_access_descriptor():
    donor = bytes((index * 17) & 0xFF for index in range(0x800))
    title_id = classic_title_id_for_romm_id(7, "gb")
    patched = _patch_exheader(donor, title_id, "CTR-N-RHGB")
    assert patched[0x1C8:0x1D0] == title_id[::-1]
    assert patched[0x200:0x208] == title_id[::-1]
    assert patched[0x400:] == donor[0x400:]
    assert patched != donor


def test_prepare_classic_rom_accepts_raw_rom():
    rom = b"GB ROM" * 64
    assert prepare_classic_rom(rom, "gb") == rom


def test_prepare_classic_rom_extracts_matching_file_from_zip():
    expected = b"GBC ROM" * 64
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
