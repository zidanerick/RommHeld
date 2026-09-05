from __future__ import annotations

from PIL import Image, ImageDraw

from romm_vita_manager.vc_art_layout import (
    ArtworkLayout,
    GBA_BANNER_LAYOUT,
    GBC_LABEL_LAYOUT,
    prepare_artwork_for_viewport,
)


def test_gbc_box_art_strips_platform_sidebar_and_fills_cartridge_label() -> None:
    # Model a typical GBC portrait box front: black GAME BOY COLOR family strip
    # at the left, with the actual game artwork occupying the remaining cover.
    artwork = Image.new("RGB", (100, 150), (28, 120, 210))
    draw = ImageDraw.Draw(artwork)
    draw.rectangle((0, 0, 14, 149), fill=(8, 8, 8))
    draw.rectangle((38, 38, 76, 108), fill=(220, 55, 35))

    result = prepare_artwork_for_viewport(artwork, (70, 74), GBC_LABEL_LAYOUT)

    assert result.size == (70, 74)
    # Nintendo's small label viewport should be filled with game art rather than
    # shrinking the complete portrait box and preserving its platform sidebar.
    assert result.getpixel((2, 37))[:3] != (8, 8, 8)
    assert result.getpixel((67, 37))[:3] != (8, 8, 8)
    assert result.getpixel((35, 37))[:3] == (220, 55, 35)


def test_gba_box_art_strips_top_masthead_before_square_crop() -> None:
    # Typical GBA cover geometry: a horizontal platform masthead above the
    # actual game art.  The official GBA donor COMMON1 contains the game label,
    # not that retail-box masthead.
    artwork = Image.new("RGB", (120, 180), (210, 50, 40))
    ImageDraw.Draw(artwork).rectangle((0, 0, 119, 22), fill=(25, 80, 210))

    result = prepare_artwork_for_viewport(artwork, (128, 128), GBA_BANNER_LAYOUT)

    assert result.size == (128, 128)
    assert result.getpixel((64, 64))[:3] == (210, 50, 40)
    # The three-pixel Nintendo-frame safety inset remains, but the visible art
    # no longer wastes the top of the label on the box's GBA masthead.
    assert result.getpixel((64, 4))[:3] == (210, 50, 40)


def test_square_art_is_not_subjected_to_box_chrome_crop() -> None:
    artwork = Image.new("RGB", (128, 128), (210, 50, 40))
    ImageDraw.Draw(artwork).rectangle((0, 0, 127, 18), fill=(25, 80, 210))

    result = prepare_artwork_for_viewport(artwork, (128, 128), GBA_BANNER_LAYOUT)

    # Square/title-screen artwork is already in the right presentation shape;
    # family box-cover stripping is intentionally portrait-only.
    assert result.getpixel((64, 4))[:3] == (25, 80, 210)


def test_uniform_scanner_border_is_trimmed_before_fitting() -> None:
    artwork = Image.new("RGB", (100, 100), (255, 255, 255))
    ImageDraw.Draw(artwork).rectangle((15, 15, 84, 84), fill=(20, 160, 70))
    layout = ArtworkLayout("cover", padding=0, trim_uniform_border=True)

    result = prepare_artwork_for_viewport(artwork, (48, 48), layout)

    # Without border trimming the green subject would occupy only ~34 pixels.
    # Conservative trimming expands it to the full viewport.
    assert result.getpixel((1, 24))[:3] == (20, 160, 70)
    assert result.getpixel((46, 24))[:3] == (20, 160, 70)
