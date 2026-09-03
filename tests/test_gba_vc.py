import io
import zipfile

from romm_vita_manager.gba_vc import (
    build_native_gba_cia,
    native_title_id_for_romm_id,
    prepare_gba_rom,
)


def test_native_title_id_is_valid_gba_vc_shape():
    title_id = native_title_id_for_romm_id(42)
    assert len(title_id) == 8
    assert title_id.hex().startswith("0004000000f")
    assert title_id.hex().endswith("00")


def test_native_title_id_is_stable():
    assert native_title_id_for_romm_id(42) == native_title_id_for_romm_id(42)
    assert native_title_id_for_romm_id(42) != native_title_id_for_romm_id(43)


def test_native_builder_rejects_blank_boot_logo_before_packaging():
    try:
        build_native_gba_cia(
            b"GBA TEST ROM",
            b"image",
            boot_logo=b"",
            title_id=native_title_id_for_romm_id(42),
            title_name="Test Game",
        )
    except ValueError as exc:
        assert "boot logo" in str(exc).lower()
    else:
        raise AssertionError("Expected blank AGB_FIRM boot logo to be rejected")


def test_prepare_gba_rom_extracts_gba_from_zip():
    raw_rom = b"GBA TEST ROM\x00" * 32
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Advance Wars (USA).gba", raw_rom)
        archive.writestr("README.txt", "metadata")

    assert prepare_gba_rom(buffer.getvalue()) == raw_rom


def test_prepare_gba_rom_rejects_zip_without_gba():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", "metadata")

    try:
        prepare_gba_rom(buffer.getvalue())
    except ValueError as exc:
        assert "does not contain a .gba ROM" in str(exc)
    else:
        raise AssertionError("Expected ZIP without a GBA ROM to be rejected")
