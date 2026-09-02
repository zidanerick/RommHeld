from romm_vita_manager.three_ds_targets import available_targets, compatible_platform, default_destination


def test_gba_exposes_native_retroarch_and_vc_targets():
    keys = [target.key for target in available_targets("gba")]
    assert keys == ["native_gba", "retroarch", "vc_cia"]


def test_gb_exposes_retroarch_and_vc_targets():
    keys = [target.key for target in available_targets("gb")]
    assert keys == ["retroarch", "vc_cia"]


def test_non_supported_platform_is_not_claimed_compatible():
    assert not compatible_platform("3ds")


def test_default_destinations_are_stable_and_explicit():
    assert default_destination("retroarch", "gba", "Metroid Fusion.gba") == "/RetroArch/roms/gba/Metroid Fusion.gba"
    assert default_destination("native_gba", "gba", "Metroid Fusion.gba") == "/roms/gba/Metroid Fusion.gba"
    assert default_destination("vc_cia", "gba", "Metroid Fusion.gba") == "/cias/Metroid Fusion.cia"
