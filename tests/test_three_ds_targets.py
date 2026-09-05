from romm_vita_manager.three_ds_targets import (
    THREE_DS_PLATFORM_SLUGS,
    RETROACHIEVEMENTS_RETROARCH_PLATFORM_SLUGS,
    RETROARCH_TARGET_PLATFORM_SLUGS,
    available_targets,
    compatible_platform,
    default_destination,
    preferred_target_key,
)


def test_gba_exposes_open_agb_native_cia_retroarch_and_vc_targets():
    keys = [target.key for target in available_targets("gba")]
    assert keys == ["open_agb_firm", "native_gba", "retroarch", "vc_cia"]


def test_software_vc_families_expose_retroarch_and_vc_targets():
    for slug in ("gb", "gbc", "nes", "gamegear", "snes"):
        keys = [target.key for target in available_targets(slug)]
        assert keys == ["retroarch", "vc_cia"]


def test_famicom_and_fds_remain_retroarch_only():
    for slug in ("famicom", "fds"):
        assert [target.key for target in available_targets(slug)] == ["retroarch"]


def test_dedicated_runtime_platforms_are_exposed_without_forcing_retroarch():
    assert [target.key for target in available_targets("nds")] == ["twilight"]
    assert [target.key for target in available_targets("virtualboy")] == ["red_viper"]
    assert [target.key for target in available_targets("n64")] == ["daedalusx64"]
    assert "n64" not in RETROARCH_TARGET_PLATFORM_SLUGS
    for slug in ("nds", "virtualboy", "n64"):
        assert slug in THREE_DS_PLATFORM_SLUGS
        assert compatible_platform(slug)


def test_3ds_exposes_existing_cia_target():
    assert compatible_platform("3ds")
    assert [target.key for target in available_targets("3ds")] == ["native_3ds_cia"]


def test_runtime_preference_chooses_dedicated_routes_by_default():
    assert preferred_target_key("gba") == "open_agb_firm"
    assert preferred_target_key("nds") == "twilight"
    assert preferred_target_key("virtualboy") == "red_viper"
    assert preferred_target_key("n64") == "daedalusx64"
    assert preferred_target_key("3ds") == "native_3ds_cia"


def test_retroachievements_preference_uses_only_verified_current_3ds_core_routes():
    for slug in ("gba", "gb", "gbc", "nes", "gamegear", "sms", "genesis", "sega32", "segacd"):
        assert slug in RETROACHIEVEMENTS_RETROARCH_PLATFORM_SLUGS
        assert preferred_target_key(slug, "retroachievements") == "retroarch"

    assert "snes" not in RETROACHIEVEMENTS_RETROARCH_PLATFORM_SLUGS
    assert preferred_target_key("snes", "retroachievements") == "vc_cia"
    assert preferred_target_key("n64", "retroachievements") == "daedalusx64"
    assert preferred_target_key("nds", "retroachievements") == "twilight"
    assert preferred_target_key("virtualboy", "retroachievements") == "red_viper"


def test_native_preference_prefers_official_vc_when_no_dedicated_native_route_exists():
    assert preferred_target_key("gbc", "native") == "vc_cia"
    assert preferred_target_key("nes", "native") == "vc_cia"
    assert preferred_target_key("famicom", "native") == "retroarch"


def test_non_supported_platform_is_not_claimed_compatible():
    assert not compatible_platform("ps2")
    assert preferred_target_key("ps2") is None


def test_default_destinations_are_stable_and_explicit():
    assert default_destination("open_agb_firm", "gba", "Metroid Fusion.gba") == "/roms/gba/Metroid Fusion.gba"
    assert default_destination("native_gba", "gba", "Metroid Fusion.gba") == "/cias/Metroid Fusion.cia"
    assert default_destination("vc_cia", "gba", "Metroid Fusion.gba") == "/cias/Metroid Fusion.cia"
    assert default_destination("twilight", "nds", "Mario Kart DS.nds") == "/roms/nds/Mario Kart DS.nds"
    assert default_destination("red_viper", "virtualboy", "Wario Land.vb") == "/roms/virtualboy/Wario Land.vb"
    assert default_destination("daedalusx64", "n64", "Mario 64.z64") == "/3ds/DaedalusX64/Roms/Mario 64.z64"
    assert default_destination("retroarch", "gba", "Metroid Fusion.gba") == "/roms/gba/Metroid Fusion.gba"
    assert default_destination("vc_cia", "gbc", "Oracle of Seasons.gbc") == "/cias/Oracle of Seasons.cia"
    assert default_destination("vc_cia", "nes", "Renegade.nes") == "/cias/Renegade.cia"
    assert default_destination("vc_cia", "gamegear", "Sonic.gg") == "/cias/Sonic.cia"
    assert default_destination("vc_cia", "snes", "Super Metroid.sfc") == "/cias/Super Metroid.cia"
    assert default_destination("native_3ds_cia", "3ds", "Metroid.3ds") == "/cias/Metroid.cia"
