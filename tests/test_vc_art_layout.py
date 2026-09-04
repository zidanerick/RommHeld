from __future__ import annotations

from PIL import Image, ImageDraw

from romm_vita_manager.vc_art_layout import (
    ArtworkLayout,
    GBA_BANNER_LAYOUT,
    GBC_LABEL_LAYOUT,
    prepare_artwork_for_viewport,
)


def test_contain_layout_keeps_artwork_inside_nintendo_label_safe_area() -> None:
    artwork = Image.new("RGB", (80, 140), (245, 245, 245))
    draw = ImageDraw.Draw(artwork)
    draw.rectangle((8, 10, 71, 129), fill=(20, 90, 210))
    draw.rectangle((24, 40, 55, 99), fill=(210, 45, 35))

    result = prepare_artwork_for_viewport(artwork, (70, 74), GBC_LABEL_LAYOUT)

    assert result.size == (70, 74)
    # The family inset/background remains around the contained art while its
    # central subject remains visible and centred inside Nintendo's viewport.
    assert result.getpixel((0, 0))[:3] == (20, 90, 210)
    assert result.getpixel((35, 37))[:3] == (210, 45, 35)


def test_gba_cover_layout_fills_square_without_portrait_letterboxing() -> None:
    artwork = Image.new("RGB", (120, 180), (250, 250, 250))
    ImageDraw.Draw(artwork).rectangle((10, 12, 109, 167), fill=(210, 50, 40))

    result = prepare_artwork_for_viewport(artwork, (128, 128), GBA_BANNER_LAYOUT)

    assert result.size == (128, 128)
    # Four-pixel safe inset is retained, but the actual artwork fills the
    # remaining square instead of appearing as a narrow portrait cover.
    assert result.getpixel((64, 64))[:3] == (210, 50, 40)
    assert result.getpixel((5, 64))[:3] == (210, 50, 40)


def test_uniform_scanner_border_is_trimmed_before_fitting() -> None:
    artwork = Image.new("RGB", (100, 100), (255, 255, 255))
    ImageDraw.Draw(artwork).rectangle((15, 15, 84, 84), fill=(20, 160, 70))
    layout = ArtworkLayout("cover", padding=0, trim_uniform_border=True)

    result = prepare_artwork_for_viewport(artwork, (48, 48), layout)

    # Without border trimming the green subject would occupy only ~34 pixels.
    # Conservative trimming expands it to the full viewport.
    assert result.getpixel((1, 24))[:3] == (20, 160, 70)
    assert result.getpixel((46, 24))[:3] == (20, 160, 70)
