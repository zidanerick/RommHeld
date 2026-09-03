from romm_vita_manager.design_tokens import BRANDS, DARK, brand_for_platform


def test_manufacturer_brand_colours_are_stable():
    assert BRANDS["nintendo"].accent == "#E60012"
    assert BRANDS["sony"].accent == "#0070D1"
    assert BRANDS["xbox"].accent == "#107C10"
    assert BRANDS["sega"].accent == "#0089CF"


def test_current_handhelds_map_to_manufacturer_family():
    assert brand_for_platform("3ds") is BRANDS["nintendo"]
    assert brand_for_platform("ds") is BRANDS["nintendo"]
    assert brand_for_platform("gba") is BRANDS["nintendo"]
    assert brand_for_platform("vita") is BRANDS["sony"]
    assert brand_for_platform("psp") is BRANDS["sony"]


def test_unknown_platform_falls_back_to_neutral():
    assert brand_for_platform("future-device") is BRANDS["neutral"]
    assert brand_for_platform(None) is BRANDS["neutral"]


def test_palette_keeps_text_and_surface_tokens_distinct():
    assert DARK.background != DARK.surface
    assert DARK.surface != DARK.surface_raised
    assert DARK.text_primary != DARK.text_secondary
