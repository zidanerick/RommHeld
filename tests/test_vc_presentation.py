from __future__ import annotations

import io

from PIL import Image, ImageDraw

import romm_vita_manager.vc_presentation as presentation


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_gbc_front_artwork_preserves_donor_cartridge_frame(monkeypatch):
    donor = Image.new("RGBA", (128, 128), (30, 30, 30, 255))
    draw = ImageDraw.Draw(donor)
    draw.rectangle((30, 20, 99, 93), fill=(180, 180, 180, 255))
    artwork = Image.new("RGB", (80, 120), (30, 90, 220))

    monkeypatch.setattr(
        presentation,
        "_donor_texture_image",
        lambda banner, name: donor.copy(),
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

    # Pixels outside Oracle-style label rectangle remain byte-identical to the
    # donor frame; the label interior receives the selected game's artwork.
    assert result.getpixel((10, 10)) == donor.getpixel((10, 10))
    assert result.getpixel((110, 64)) == donor.getpixel((110, 64))
    assert result.getpixel((64, 55)) != donor.getpixel((64, 55))


def test_official_badge_retains_left_vc_chrome_and_replaces_title(monkeypatch):
    donor = Image.new("LA", (256, 64), (220, 255))
    draw = ImageDraw.Draw(donor)
    draw.rectangle((0, 0, 94, 63), fill=(90, 255))
    # Synthetic donor-specific dark text in the right title panel.
    draw.rectangle((130, 18, 205, 24), fill=(10, 255))
    draw.rectangle((145, 42, 190, 47), fill=(10, 255))

    monkeypatch.setattr(
        presentation,
        "_donor_texture_image",
        lambda banner, name: donor.copy(),
    )
    result = Image.open(
        io.BytesIO(
            presentation.prepare_official_vc_badge(
                b"synthetic-donor",
                "Pokémon Crystal",
                "gbc",
                release_year=2001,
            )
        )
    ).convert("LA")

    # The family-neutral Virtual Console/chrome region comes straight from the
    # donor. Only the title panel is cleaned and redrawn.
    assert result.crop((0, 0, 90, 64)).tobytes() == donor.crop((0, 0, 90, 64)).tobytes()
    assert result.crop((100, 5, 250, 59)).tobytes() != donor.crop((100, 5, 250, 59)).tobytes()
    # Rendered title/year create dark glyph pixels in the cleaned panel.
    assert min(result.crop((100, 5, 250, 59)).getchannel("L").getdata()) < 80


def test_official_icon_preserves_retail_frame_and_replaces_interior():
    from agbcia.formats import smdh

    width, height = smdh.ICON_LARGE_DIMENSIONS
    large = Image.new("RGB", (width, height), (20, 20, 20))
    ImageDraw.Draw(large).rectangle((4, 4, width - 5, height - 5), fill=(180, 30, 30))
    small = Image.new("RGB", smdh.ICON_SMALL_DIMENSIONS, (20, 20, 20))
    donor = smdh.build(
        smdh.Smdh(
            titles={},
            icon_small=small.tobytes(),
            icon_large=large.tobytes(),
        )
    )
    artwork = Image.new("RGB", (90, 140), (20, 80, 220))

    result = Image.open(
        io.BytesIO(presentation.prepare_official_vc_icon_artwork(donor, _png(artwork)))
    ).convert("RGBA")

    assert result.size == (48, 48)
    assert result.getpixel((0, 0))[:3] == large.getpixel((0, 0))
    assert result.getpixel((47, 47))[:3] == large.getpixel((47, 47))
    assert result.getpixel((24, 24))[:3] != large.getpixel((24, 24))
