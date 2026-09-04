from romm_vita_manager.classic_vc_title_fix import hardware_safe_classic_title_id


def _unique_id(title_id: bytes) -> int:
    low = int.from_bytes(title_id[4:], "big")
    assert (low & 0xFF) == 0
    return (low >> 8) & 0xFFFFFF


def test_classic_title_id_uses_normal_application_unique_id_range() -> None:
    for family in ("gb", "gbc"):
        title_id = hardware_safe_classic_title_id(42, family)
        assert title_id.hex().startswith("00040000")
        uid = _unique_id(title_id)
        assert 0x000300 <= uid <= 0x0F7FFF
        assert 0x0E0000 <= uid <= 0x0EFFFF


def test_classic_title_id_is_stable_and_family_specific() -> None:
    assert hardware_safe_classic_title_id(42, "gb") == hardware_safe_classic_title_id(42, "gb")
    assert hardware_safe_classic_title_id(42, "gb") != hardware_safe_classic_title_id(42, "gbc")
    assert hardware_safe_classic_title_id(42, "gb") != hardware_safe_classic_title_id(43, "gb")
