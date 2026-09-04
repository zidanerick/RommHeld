from __future__ import annotations

import io
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from .vc_art_layout import (
    GBA_BANNER_LAYOUT,
    GBC_LABEL_LAYOUT,
    GB_LABEL_LAYOUT,
    ICON_LAYOUT,
    prepare_artwork_for_viewport,
)

if TYPE_CHECKING:
    from agbcia.banner.image import ImageSource


@dataclass(frozen=True, slots=True)
class VcPresentationProfile:
    family: str
    front_label_rect: tuple[int, int, int, int] | None
    show_release_year: bool


_PROFILES = {
    # Rectangles were measured from the user-supplied retail European donors.
    # Everything outside these rectangles is retained from the donor texture,
    # including the actual GB/GBC cartridge shell and Nintendo branding.
    "gb": VcPresentationProfile("gb", (28, 20, 101, 87), True),
    "gbc": VcPresentationProfile("gbc", (30, 20, 100, 94), True),
    # The retail GBA donor's COMMON1 is itself the game-specific square label;
    # the cartridge/box geometry lives in the donor CGFX scene, so no inner
    # rectangle is retained here.
    "gba": VcPresentationProfile("gba", None, False),
}


def presentation_profile(family: str) -> VcPresentationProfile:
    key = family.strip().lower()
    try:
        return _PROFILES[key]
    except KeyError:
        raise ValueError(f"No Virtual Console presentation profile for {family!r}.") from None


def _load_image(source: "ImageSource") -> Image.Image:
    try:
        from agbcia.banner.image import load_image
    except ImportError as exc:
        raise RuntimeError("Virtual Console presentation requires the agbcia package.") from exc
    return load_image(source)


def _tile_offset(x: int, y: int, width: int) -> int:
    tile_index = (y >> 3) * (width >> 3) + (x >> 3)
    within_tile = (
        (x & 1)
        | ((y & 1) << 1)
        | ((x & 2) << 1)
        | ((y & 2) << 2)
        | ((x & 4) << 2)
        | ((y & 4) << 3)
    )
    return (tile_index << 6) + within_tile


def _decode_rgba8(raw: bytes, width: int, height: int) -> Image.Image:
    required = width * height * 4
    if len(raw) < required:
        raise ValueError("Donor RGBA8 texture is truncated.")
    out = bytearray(required)
    for y in range(height):
        for x in range(width):
            src = _tile_offset(x, y, width) * 4
            alpha, blue, green, red = raw[src : src + 4]
            dst = (y * width + x) * 4
            out[dst : dst + 4] = bytes((red, green, blue, alpha))
    return Image.frombytes("RGBA", (width, height), bytes(out))


def _decode_la8(raw: bytes, width: int, height: int) -> Image.Image:
    required = width * height * 2
    if len(raw) < required:
        raise ValueError("Donor LA8 texture is truncated.")
    out = bytearray(required)
    for y in range(height):
        for x in range(width):
            src = _tile_offset(x, y, width) * 2
            alpha, luminance = raw[src : src + 2]
            dst = (y * width + x) * 2
            out[dst : dst + 2] = bytes((luminance, alpha))
    return Image.frombytes("LA", (width, height), bytes(out))


def _donor_texture_image(donor_banner: bytes, name: str) -> Image.Image:
    """Decode one of the retail donor's actual banner textures.

    No Nintendo texture is bundled with RommHeld. The image is decoded at build
    time from the user's cached donor banner and used only as a template for the
    newly generated title.
    """
    try:
        from agbcia.formats import cbmd, cgfx, lz11
    except ImportError as exc:
        raise RuntimeError("Donor-derived Virtual Console presentation requires agbcia.") from exc

    common = lz11.decompress(cbmd.extract_common_cgfx(donor_banner))
    texture = cgfx.find_texture(common, name)
    raw = common[
        texture.raw_buffer_offset : texture.raw_buffer_offset + texture.raw_buffer_length
    ]
    if texture.hw_format == 0:  # PICA RGBA8
        return _decode_rgba8(raw, texture.width, texture.height)
    if texture.hw_format == 5:  # PICA LA8
        return _decode_la8(raw, texture.width, texture.height)
    raise ValueError(
        f"Unsupported donor texture format for {name}: {texture.hw_format} "
        f"({texture.width}x{texture.height})."
    )


def _png(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def prepare_official_vc_front_artwork(
    donor_banner: bytes,
    artwork: "ImageSource",
    family: str,
) -> bytes:
    """Build COMMON1 while respecting the actual Nintendo artwork viewport.

    GB/GBC keep the donor cartridge shell and place the complete source artwork
    inside the measured label safe area with a small inset. GBA's donor scene
    expects a square label, so portrait box art is conservatively cropped to
    that square after uniform scanner margins are trimmed. This prevents source
    covers from touching or visibly overflowing Nintendo's frame.
    """
    profile = presentation_profile(family)
    source = _load_image(artwork).convert("RGBA")
    donor = _donor_texture_image(donor_banner, "COMMON1").convert("RGBA")

    if profile.front_label_rect is None:
        replacement = prepare_artwork_for_viewport(
            source,
            donor.size,
            GBA_BANNER_LAYOUT,
        )
        return _png(replacement)

    left, top, right, bottom = profile.front_label_rect
    if not (0 <= left < right <= donor.width and 0 <= top < bottom <= donor.height):
        raise ValueError("Virtual Console donor label rectangle is outside COMMON1.")

    layout = GB_LABEL_LAYOUT if profile.family == "gb" else GBC_LABEL_LAYOUT
    replacement = prepare_artwork_for_viewport(
        source,
        (right - left, bottom - top),
        layout,
    )
    result = donor.copy()
    result.alpha_composite(replacement, (left, top))
    return _png(result)


def _font(size: int, *, bold: bool = True) -> ImageFont.ImageFont:
    candidates = (
        "DejaVuSansCondensed-Bold.ttf" if bold else "DejaVuSansCondensed.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf",
        "Arial Bold.ttf" if bold else "Arial.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int, max_lines: int) -> list[str]:
    words = text.replace("\n", " ").split()
    if not words:
        return ["Untitled Game"]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        box = draw.textbbox((0, 0), candidate, font=font)
        if current and box[2] - box[0] > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) <= max_lines:
        return lines
    return lines[: max_lines - 1] + [" ".join(lines[max_lines - 1 :])]


def _clear_badge_title_panel(image: Image.Image) -> Image.Image:
    """Remove donor-specific text while retaining its exact badge chrome."""
    badge = image.convert("LA").copy()
    width, height = badge.size
    left = max(1, round(width * 0.375))
    top = max(2, round(height * 0.08))
    bottom = min(height - 3, round(height * 0.91))
    right = width - max(3, round(width * 0.02))

    for x in range(left, right):
        top_l, top_a = badge.getpixel((x, top))
        bottom_l, bottom_a = badge.getpixel((x, bottom))
        span = max(1, bottom - top)
        for y in range(top, bottom + 1):
            ratio = (y - top) / span
            lum = round(top_l + (bottom_l - top_l) * ratio)
            alpha = round(top_a + (bottom_a - top_a) * ratio)
            badge.putpixel((x, y), (lum, alpha))
    return badge


def prepare_official_vc_badge(
    donor_banner: bytes,
    title: str,
    family: str,
    *,
    release_year: int | None = None,
) -> bytes:
    """Rebuild COMMON2 using the donor's real Virtual Console badge."""
    profile = presentation_profile(family)
    badge = _clear_badge_title_panel(_donor_texture_image(donor_banner, "COMMON2"))
    width, height = badge.size
    draw = ImageDraw.Draw(badge)
    content_left = round(width * 0.385)
    content_right = width - round(width * 0.025)
    content_width = content_right - content_left

    clean_title = " ".join(str(title).replace("\x00", " ").split()).strip() or "Untitled Game"
    show_release = profile.show_release_year and release_year is not None and 1900 <= release_year <= 2200

    chosen_font = _font(15)
    chosen_lines = [clean_title]
    title_height_limit = 38 if show_release else 52
    for size in range(16, 9, -1):
        candidate_font = _font(size)
        lines = _wrap_lines(draw, clean_title, candidate_font, content_width, 2)
        if len(lines) > 2:
            continue
        boxes = [draw.textbbox((0, 0), line, font=candidate_font) for line in lines]
        total = sum(box[3] - box[1] for box in boxes) + max(0, len(lines) - 1)
        if all(box[2] - box[0] <= content_width for box in boxes) and total <= title_height_limit:
            chosen_font = candidate_font
            chosen_lines = lines
            break

    boxes = [draw.textbbox((0, 0), line, font=chosen_font) for line in chosen_lines]
    heights = [box[3] - box[1] for box in boxes]
    title_total = sum(heights) + max(0, len(chosen_lines) - 1)
    title_top = 5 if show_release else max(5, (height - title_total) // 2)
    y = title_top
    for line, box, line_height in zip(chosen_lines, boxes, heights):
        line_width = box[2] - box[0]
        x = content_left + max(0, (content_width - line_width) // 2)
        draw.text((x, y), line, font=chosen_font, fill=(28, 255))
        y += line_height + 1

    if show_release:
        release = f"Released: {release_year}"
        release_font = _font(12, bold=True)
        box = draw.textbbox((0, 0), release, font=release_font)
        x = content_left + max(0, (content_width - (box[2] - box[0])) // 2)
        y = min(height - (box[3] - box[1]) - 5, 43)
        draw.text((x, y), release, font=release_font, fill=(28, 255))

    return _png(badge)


def prepare_official_vc_icon_artwork(
    donor_icon: bytes,
    artwork: "ImageSource",
) -> bytes:
    """Retain the retail SMDH frame and fill its inner artwork viewport."""
    try:
        from agbcia.formats import smdh as smdh_format
    except ImportError as exc:
        raise RuntimeError("Donor-derived Virtual Console icons require agbcia.") from exc

    donor = smdh_format.parse(donor_icon)
    frame = Image.frombytes("RGB", smdh_format.ICON_LARGE_DIMENSIONS, donor.icon_large).convert("RGBA")
    source = _load_image(artwork).convert("RGBA")
    inset = 4
    interior_size = frame.width - inset * 2
    if interior_size <= 0:
        raise ValueError("Donor SMDH icon is too small for its retail frame.")
    interior = prepare_artwork_for_viewport(
        source,
        (interior_size, interior_size),
        ICON_LAYOUT,
    )
    result = frame.copy()
    result.alpha_composite(interior, (inset, inset))
    return _png(result)
