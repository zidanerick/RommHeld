from __future__ import annotations

import io

from PIL import Image, ImageDraw

import romm_vita_manager.vc_presentation as presentation


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_remaining_vc_profiles_match_supplied_retail_donor_textures() -> None:
    nes = presentation.presentation_profile("nes")
    snes = presentation.presentation_profile("snes")
    gamegear = presentation.presentation_profile("gamegear")

    assert nes.artwork_texture == "COMMON1"
    assert nes.badge_texture == "COMMON2"
    assert nes.badge_size == (256, 64)
    assert nes.show_release_year

    assert snes.artwork_texture == "COMMON1"
    assert snes.badge_texture == "EUR_EN2"
    assert snes.badge_size == (256, 64)
    assert "EUR_RU2" in snes.badge_texture_alternates
    assert snes.show_release_year

    assert gamegear.artwork_texture == "COMMON2"
    assert gamegear.badge_texture == "TitlePlate"
    assert gamegear.badge_size == (256, 64)
    assert gamegear.show_release_year
    assert nes.icon_mode == "framed"
    assert snes.icon_mode == "framed"
    assert gamegear.icon_mode == "full"


def test_snes_profile_patches_every_supplied_european_locale_plate() -> None:
    names = presentation.badge_texture_names(presentation.presentation_profile("snes"))

    assert names == (
        "EUR_EN2",
        "EUR_FR2",
        "EUR_GE2",
        "EUR_IT2",
        "EUR_SP2",
        "EUR_DU2",
        "EUR_PO2",
        "EUR_RU2",
    )


def test_rgb565_texture_decoder_handles_tiled_primary_mip() -> None:
    width = height = 8
    red565 = 0xF800
    raw = red565.to_bytes(2, "little") * (width * height)
    result = presentation._decode_rgb565(raw, width, height)

    assert result.size == (8, 8)
    assert result.getpixel((0, 0)) == (255, 0, 0)
    assert result.getpixel((7, 7)) == (255, 0, 0)


def test_l4_texture_decoder_handles_retail_nes_dummy_texture_format() -> None:
    raw = bytearray(32)
    raw[0] = 0xE1
    result = presentation._decode_l4(bytes(raw), 8, 8)

    assert result.mode == "L"
    assert result.getpixel((0, 0)) == 0x11
    assert result.getpixel((1, 0)) == 0xEE


def test_gbc_front_artwork_preserves_donor_cartridge_frame(monkeypatch):
    donor = Image.new("RGBA", (128, 128), (30, 30, 30, 255))
    draw = ImageDraw.Draw(donor)
    draw.rectangle((30, 20, 99, 93), fill=(180, 180, 180, 255))
    artwork = Image.new("RGB", (80, 120), (30, 90, 220))

    monkeypatch.setattr(
        presentation,
        "_donor_texture_image",
        lambda banner, name, **kwargs: donor.copy(),
    )
    result = Image.open(
        io.BytesIO(
            presentation.prepare_official_vc_front_artwork(
                b"synthetic-donor",
                _png(artwork),
                "gbc",
            )
        )
    ).convert("RGBA")

    assert result.getpixel((10, 10)) == donor.getpixel((10, 10))
    assert result.getpixel((110, 64)) == donor.getpixel((110, 64))
    assert result.getpixel((64, 55)) != donor.getpixel((64, 55))


def test_gamegear_front_artwork_uses_common2_game_texture(monkeypatch):
    donor = Image.new("RGBA", (128, 128), (20, 20, 20, 255))
    artwork = Image.new("RGB", (120, 180), (30, 100, 220))
    seen: list[str] = []

    def texture(_banner: bytes, name: str, **_kwargs) -> Image.Image:
        seen.append(name)
        return donor.copy()

    monkeypatch.setattr(presentation, "_donor_texture_image", texture)
    result = Image.open(
        io.BytesIO(
            presentation.prepare_official_vc_front_artwork(
                b"synthetic-donor", _png(artwork), "gamegear"
            )
        )
    ).convert("RGBA")

    assert seen == ["COMMON2"]
    assert result.size == donor.size
    assert result.getpixel((64, 64))[:3] == (30, 100, 220)


def test_donor_texture_selection_skips_wrong_size_same_name(monkeypatch) -> None:
    common = b"common"
    english = b"english"
    monkeypatch.setattr(presentation, "_banner_cgfx_slots", lambda _banner: [common, english])

    def texture(scene: bytes, name: str) -> Image.Image:
        assert name == "COMMON2"
        if scene == common:
            return Image.new("L", (8, 8), 255)
        return Image.new("LA", (256, 64), (220, 255))

    monkeypatch.setattr(presentation, "_texture_image_from_cgfx", texture)
    selected = presentation._donor_texture_image(
        b"synthetic-donor",
        "COMMON2",
        expected_size=(256, 64),
    )

    assert selected.size == (256, 64)


def test_official_badge_retains_left_vc_chrome_and_replaces_title(monkeypatch):
    donor = Image.new("LA", (256, 64), (220, 255))
    draw = ImageDraw.Draw(donor)
    draw.rectangle((0, 0, 94, 63), fill=(90, 255))
    draw.rectangle((130, 18, 205, 24), fill=(10, 255))
    draw.rectangle((145, 42, 190, 47), fill=(10, 255))

    monkeypatch.setattr(
        presentation,
        "_donor_badge_texture_image",
        lambda banner, profile: donor.copy(),
    )
    badge = presentation.prepare_official_vc_badge(
        b"synthetic-donor",
        "Pokémon Crystal",
        "gbc",
        release_year=2001,
    )
    assert badge is not None
    result = Image.open(io.BytesIO(badge)).convert("LA")

    assert result.crop((0, 0, 90, 64)).tobytes() == donor.crop((0, 0, 90, 64)).tobytes()
    assert result.crop((100, 5, 250, 59)).tobytes() != donor.crop((100, 5, 250, 59)).tobytes()
    assert result.crop((100, 5, 250, 59)).getchannel("L").getextrema()[0] < 80


def test_nes_badge_uses_localized_256x64_template(monkeypatch) -> None:
    donor = Image.new("LA", (256, 64), (220, 255))
    ImageDraw.Draw(donor).rectangle((0, 0, 94, 63), fill=(90, 255))
    seen: list[tuple[str, tuple[int, int] | None]] = []

    def texture(_banner: bytes, name: str, *, expected_size=None) -> Image.Image:
        seen.append((name, expected_size))
        return donor.copy()

    monkeypatch.setattr(presentation, "_donor_texture_image", texture)
    badge = presentation.prepare_official_vc_badge(
        b"synthetic-donor",
        "Ghostbusters",
        "nes",
        release_year=1988,
    )
    assert badge is not None
    assert seen == [("COMMON2", (256, 64))]
    assert Image.open(io.BytesIO(badge)).size == (256, 64)


def test_gamegear_badge_uses_titleplate_template(monkeypatch) -> None:
    donor = Image.new("LA", (256, 64), (220, 255))
    ImageDraw.Draw(donor).rectangle((0, 0, 94, 63), fill=(90, 255))
    seen: list[tuple[str, tuple[int, int] | None]] = []

    def texture(_banner: bytes, name: str, *, expected_size=None) -> Image.Image:
        seen.append((name, expected_size))
        return donor.copy()

    monkeypatch.setattr(presentation, "_donor_texture_image", texture)
    badge = presentation.prepare_official_vc_badge(
        b"synthetic-donor",
        "Sonic the Hedgehog 2",
        "gamegear",
        release_year=1992,
    )
    assert badge is not None
    assert seen == [("TitlePlate", (256, 64))]


def test_snes_badge_uses_english_plate_template_first(monkeypatch) -> None:
    donor = Image.new("LA", (256, 64), (220, 255))
    ImageDraw.Draw(donor).rectangle((0, 0, 94, 63), fill=(90, 255))
    seen: list[str] = []

    def texture(_banner: bytes, name: str, *, expected_size=None) -> Image.Image:
        seen.append(name)
        if name != "EUR_EN2":
            raise ValueError("unexpected fallback")
        assert expected_size == (256, 64)
        return donor.copy()

    monkeypatch.setattr(presentation, "_donor_texture_image", texture)
    badge = presentation.prepare_official_vc_badge(
        b"synthetic-donor",
        "Synthetic SNES Game",
        "snes",
        release_year=1995,
    )
    assert badge is not None
    assert seen == ["EUR_EN2"]


def _synthetic_donor_icon(frame_colour=(20, 20, 20), interior_colour=(180, 30, 30)) -> tuple[bytes, Image.Image]:
    from agbcia.formats import smdh

    width, height = smdh.ICON_LARGE_DIMENSIONS
    large = Image.new("RGB", (width, height), frame_colour)
    ImageDraw.Draw(large).rectangle((4, 4, width - 5, height - 5), fill=interior_colour)
    small = Image.new("RGB", smdh.ICON_SMALL_DIMENSIONS, frame_colour)
    donor = smdh.build(
        smdh.Smdh(
            titles={},
            icon_small=small.tobytes(),
            icon_large=large.tobytes(),
        )
    )
    parsed_donor = smdh.parse(donor)
    decoded_large = Image.frombytes("RGB", smdh.ICON_LARGE_DIMENSIONS, parsed_donor.icon_large)
    return donor, decoded_large


def test_official_icon_preserves_retail_frame_and_replaces_interior():
    donor, decoded_large = _synthetic_donor_icon()
    artwork = Image.new("RGB", (90, 140), (20, 80, 220))

    result = Image.open(
        io.BytesIO(presentation.prepare_official_vc_icon_artwork(donor, _png(artwork), "gba"))
    ).convert("RGBA")

    assert result.size == (48, 48)
    assert result.getpixel((0, 0))[:3] == decoded_large.getpixel((0, 0))
    assert result.getpixel((47, 47))[:3] == decoded_large.getpixel((47, 47))
    assert result.getpixel((24, 24))[:3] != decoded_large.getpixel((24, 24))


def test_gamegear_icon_uses_full_art_instead_of_donor_frame() -> None:
    donor, decoded_large = _synthetic_donor_icon(frame_colour=(10, 10, 10))
    artwork = Image.new("RGB", (64, 64), (30, 110, 220))

    result = Image.open(
        io.BytesIO(
            presentation.prepare_official_vc_icon_artwork(
                donor,
                _png(artwork),
                "gamegear",
            )
        )
    ).convert("RGBA")

    assert result.size == (48, 48)
    assert result.getpixel((0, 0))[:3] != decoded_large.getpixel((0, 0))
    assert result.getpixel((24, 24))[:3] == (30, 110, 220)
