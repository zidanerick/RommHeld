from romm_vita_manager.classic_vc_root_fix import install


def test_classic_romfs_root_parent_points_to_self() -> None:
    install()

    from romm_vita_manager import classic_vc

    romfs = classic_vc.build_romfs({"/rom/TEST.000": b"ROM"})
    level3 = classic_vc._find_level3_offset(romfs)
    root_parent = int.from_bytes(romfs[level3 + 0x28 : level3 + 0x2C], "little")
    root_sibling = int.from_bytes(romfs[level3 + 0x2C : level3 + 0x30], "little")

    assert root_parent == 0
    assert root_sibling == 0xFFFFFFFF
