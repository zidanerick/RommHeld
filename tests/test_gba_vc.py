from romm_vita_manager.gba_boot_logo import LOGO_REGION_SIZE, bundled_boot_logo
from romm_vita_manager.gba_vc import native_title_id_for_romm_id


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
