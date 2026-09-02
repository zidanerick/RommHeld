from romm_vita_manager.gba_vc import native_title_id_for_romm_id


def test_native_title_id_is_valid_gba_vc_shape():
    title_id = native_title_id_for_romm_id(42)
    assert len(title_id) == 8
    assert title_id.hex().startswith("0004000000f")
    assert title_id.hex().endswith("00")


def test_native_title_id_is_stable():
    assert native_title_id_for_romm_id(42) == native_title_id_for_romm_id(42)
    assert native_title_id_for_romm_id(42) != native_title_id_for_romm_id(43)
