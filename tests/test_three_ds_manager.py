from romm_vita_manager.three_ds_paths import default_3ds_destination


def test_default_3ds_destination_for_nds():
    assert default_3ds_destination("Mario.nds", ".nds") == "/roms/nds/Mario.nds"


def test_default_3ds_destination_for_gba():
    assert default_3ds_destination("Metroid.gba", ".gba") == "/roms/gba/Metroid.gba"


def test_default_3ds_destination_leaves_other_formats_explicit():
    assert default_3ds_destination("Homebrew.3dsx", ".3dsx") == "Homebrew.3dsx"
    assert default_3ds_destination("Title.cia", ".cia") == "Title.cia"
