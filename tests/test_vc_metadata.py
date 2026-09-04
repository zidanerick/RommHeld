from romm_vita_manager.vc_metadata import normalize_vc_metadata


def test_vc_metadata_normalizes_visible_title_fields() -> None:
    metadata = normalize_vc_metadata(
        "  Pokémon   Crystal™  ",
        long_title="  Pokémon   Crystal Version  ",
        publisher=" Nintendo  ",
    )
    assert metadata.short_title == "Pokémon Crystal™"
    assert metadata.long_title == "Pokémon Crystal Version"
    assert metadata.publisher == "Nintendo"
    assert metadata.banner_title == metadata.short_title


def test_vc_metadata_repairs_common_utf8_mojibake() -> None:
    metadata = normalize_vc_metadata("PokÃ©mon Card GB2: GR Dan Sanjou!")
    assert metadata.short_title == "Pokémon Card GB2: GR Dan Sanjou!"
    assert metadata.banner_title == "Pokémon Card GB2: GR Dan Sanjou!"


def test_vc_metadata_keeps_legitimate_unicode_unchanged() -> None:
    metadata = normalize_vc_metadata("Pokémon Pinball", publisher="Nintendo")
    assert metadata.short_title == "Pokémon Pinball"
    assert metadata.publisher == "Nintendo"


def test_vc_metadata_normalizes_combining_characters() -> None:
    metadata = normalize_vc_metadata("Poke\u0301mon")
    assert metadata.short_title == "Pokémon"


def test_vc_metadata_never_emits_blank_title() -> None:
    metadata = normalize_vc_metadata(" \x00  ", long_title="", publisher="")
    assert metadata.short_title == "Untitled Game"
    assert metadata.long_title == "Untitled Game"
    assert metadata.banner_title == "Untitled Game"
    assert metadata.publisher == ""


def test_classic_assets_activate_hardware_and_presentation_layers() -> None:
    # Importing the cache layer is part of the real deployment path and must
    # expose the hardware-safe runtime plus the donor-derived visual frame.
    from romm_vita_manager import classic_vc
    from romm_vita_manager import classic_vc_assets  # noqa: F401

    fields = classic_vc.ClassicVcRuntime.__dataclass_fields__
    assert "donor_banner" in fields
    assert "donor_icon" in fields
    romfs = classic_vc.build_romfs({"/rom/TEST.000": b"ROM"})
    assert int.from_bytes(romfs[0x1000:0x1004], "little") == 0x28
