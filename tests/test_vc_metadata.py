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


def test_vc_metadata_never_emits_blank_title() -> None:
    metadata = normalize_vc_metadata(" \x00  ", long_title="", publisher="")
    assert metadata.short_title == "Untitled Game"
    assert metadata.long_title == "Untitled Game"
    assert metadata.banner_title == "Untitled Game"
    assert metadata.publisher == ""


def test_classic_assets_activates_hardware_runtime_patch() -> None:
    # Importing the cache layer is part of the real deployment path and must
    # install the GB/GBC hardware correction before cached runtimes are loaded.
    from romm_vita_manager import classic_vc
    from romm_vita_manager import classic_vc_assets  # noqa: F401

    assert "donor_banner" in classic_vc.ClassicVcRuntime.__dataclass_fields__
    romfs = classic_vc.build_romfs({"/rom/TEST.000": b"ROM"})
    assert int.from_bytes(romfs[0x1000:0x1004], "little") == 0x28
