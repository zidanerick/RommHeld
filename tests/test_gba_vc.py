import io
import zipfile

from romm_vita_manager.gba_boot_logo import LOGO_REGION_SIZE, bundled_boot_logo
from romm_vita_manager.gba_vc import native_title_id_for_romm_id, prepare_gba_rom


def test_native_title_id_is_valid_gba_vc_shape():
    title_id = native_title_id_for_romm_id(42)
    assert len(title_id) == 8
    assert title_id.hex().startswith("0004000000f")
    assert title_id.hex().endswith("00")


def test_native_title_id_is_stable():
    assert native_title_id_for_romm_id(42) == native_title_id_for_romm_id(42)
    assert native_title_id_for_romm_id(42) != native_title_id_for_romm_id(43)


def test_bundled_boot_logo_has_native_logo_region_size():
    logo = bundled_boot_logo()
    assert len(logo) == LOGO_REGION_SIZE == 0x2000


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
