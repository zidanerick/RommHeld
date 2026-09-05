from __future__ import annotations

import io
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from .vc_art_layout import (
    GAME_GEAR_ICON_LAYOUT,
    ICON_LAYOUT,
    banner_layout_for_family,
    prepare_artwork_for_viewport,
)

if TYPE_CHECKING:
    from agbcia.banner.image import ImageSource


@dataclass(frozen=True, slots=True)
class VcPresentationProfile:
    """Donor-derived HOME Menu presentation contract for one VC family."""

    family: str
    artwork_texture: str
    front_label_rect: tuple[int, int, int, int] | None
    badge_texture: str | None
    show_release_year: bool
    icon_mode: str = "framed"


_PROFILES = {
    "gb": VcPresentationProfile("gb", "COMMON1", (28, 20, 101, 87), "COMMON2", True),
    "gbc": VcPresentationProfile("gbc", "COMMON1", (30, 20, 100, 94), "COMMON2", True),
    "gba": VcPresentationProfile("gba", "COMMON1", None, "COMMON2", False),
    # Renegade keeps its 3D NES/game scene in common, but the visible 256x64
    # Virtual Console title plaque is COMMON2 in the populated language scenes.
    "nes": VcPresentationProfile("nes", "COMMON1", None, "COMMON2", True),
    "snes": VcPresentationProfile("snes", "COMMON1", None, None, False),
    # Sonic 2 keeps COMMON3 as the Game Gear shell. Localized scenes use
    # TitlePlate for the lower VC/title plaque and may repeat COMMON2 artwork.
    "gamegear": VcPresentationProfile(
        "gamegear", "COMMON2", None, "TitlePlate", True, icon_mode="full"
    ),
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


def _decode_rgb565(raw: bytes, width: int, height: int) -> Image.Image:
    required = width * height * 2
    if len(raw) < required:
        raise ValueError("Donor RGB565 texture is truncated.")
    out = bytearray(width * height * 3)
    for y in range(height):
        for x in range(width):
            src = _tile_offset(x, y, width) * 2
            value = int.from_bytes(raw[src : src + 2], "little")
            red = ((value >> 11) & 0x1F) * 255 // 0x1F
            green = ((value >> 5) & 0x3F) * 255 // 0x3F
            blue = (value & 0x1F) * 255 // 0x1F
            dst = (y * width + x) * 3
            out[dst : dst + 3] = bytes((red, green, blue))
    return Image.frombytes("RGB", (width, height), bytes(out))


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


def _decode_l4(raw: bytes, width: int, height: int) -> Image.Image:
    """Decode Nintendo/PICA200 tiled 4-bit luminance texture data."""
    texels = width * height
    required = (texels + 1) // 2
    if len(raw) < required:
        raise ValueError("Donor L4 texture is truncated.")
    out = bytearray(texels)
    for y in range(height):
        for x in range(width):
            texel = _tile_offset(x, y, width)
            packed = raw[texel >> 1]
            nibble = (packed >> 4) & 0x0F if texel & 1 else packed & 0x0F
            out[y * width + x] = nibble * 0x11
    return Image.frombytes("L", (width, height), bytes(out))


def _banner_cgfx_slots(donor_banner: bytes) -> list[bytes]:
    """Return every populated donor CBMD language scene, common first."""
    try:
        from agbcia.formats import lz11
    except ImportError as exc:
        raise RuntimeError("Donor-derived Virtual Console presentation requires agbcia.") from exc
    if len(donor_banner) < 0x88 or donor_banner[:4] != b"CBMD":
        raise ValueError("Virtual Console donor banner is not a valid CBMD container.")
    scenes: list[bytes] = []
    for index in range(14):
        offset = int.from_bytes(donor_banner[0x08 + index * 4 : 0x0C + index * 4], "little")
        if offset:
            if offset >= len(donor_banner):
                raise ValueError("Virtual Console donor banner has an invalid language-scene offset.")
            scenes.append(lz11.decompress(donor_banner[offset:]))
    if not scenes:
        raise ValueError("Virtual Console donor banner has no CGFX presentation scenes.")
    return scenes


def _texture_image_from_cgfx(scene: bytes, name: str) -> Image.Image:
    try:
        from agbcia.formats import cgfx
    except ImportError as exc:
        raise RuntimeError("Donor-derived Virtual Console presentation requires agbcia.") from exc
    texture = cgfx.find_texture(scene, name)
    raw = scene[texture.raw_buffer_offset : texture.raw_buffer_offset + texture.raw_buffer_length]
    if texture.hw_format == 0:
        return _decode_rgba8(raw, texture.width, texture.height)
    if texture.hw_format == 3:
        return _decode_rgb565(raw, texture.width, texture.height)
    if texture.hw_format == 5:
        return _decode_la8(raw, texture.width, texture.height)
    if texture.hw_format == 10:
        return _decode_l4(raw, texture.width, texture.height)
    raise ValueError(
        f"Unsupported donor texture format for {name}: {texture.hw_format} "
        f"({texture.width}x{texture.height})."
    )


def _donor_texture_image(donor_banner: bytes, name: str) -> Image.Image:
    """Decode a texture from common, falling back to localized donor scenes."""
    last_error: Exception | None = None
    for scene in _banner_cgfx_slots(donor_banner):
        try:
            return _texture_image_from_cgfx(scene, name)
        except Exception as exc:
            last_error = exc
    raise ValueError(f"Donor banner has no usable texture named {name!r}.") from last_error


def _png(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def prepare_official_vc_front_artwork(
    donor_banner: bytes,
    artwork: "ImageSource",
    family: str,
) -> bytes:
    profile = presentation_profile(family)
    source = _load_image(artwork).convert("RGBA")
    donor = _donor_texture_image(donor_banner, profile.artwork_texture).convert("RGBA")
    layout = banner_layout_for_family(profile.family)

    if profile.front_label_rect is None:
        return _png(prepare_artwork_for_viewport(source, donor.size, layout))

    left, top, right, bottom = profile.front_label_rect
    if not (0 <= left < right <= donor.width and 0 <= top < bottom <= donor.height):
        raise ValueError("Virtual Console donor label rectangle is outside its artwork texture.")
    replacement = prepare_artwork_for_viewport(source, (right - left, bottom - top), layout)
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


def _wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    width: int,
    max_lines: int,
) -> list[str]:
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
) -> bytes | None:
    profile = presentation_profile(family)
    if profile.badge_texture is None:
        return None

    badge = _clear_badge_title_panel(_donor_texture_image(donor_banner, profile.badge_texture))
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
    family: str | None = None,
) -> bytes:
    try:
        from agbcia.formats import smdh as smdh_format
    except ImportError as exc:
        raise RuntimeError("Donor-derived Virtual Console icons require agbcia.") from exc

    donor = smdh_format.parse(donor_icon)
    source = _load_image(artwork).convert("RGBA")
    profile = presentation_profile(family) if family is not None else None
    icon_mode = profile.icon_mode if profile is not None else "framed"

    if icon_mode == "full":
        full = prepare_artwork_for_viewport(
            source,
            smdh_format.ICON_LARGE_DIMENSIONS,
            GAME_GEAR_ICON_LAYOUT,
        )
        return _png(full)
    if icon_mode != "framed":
        raise ValueError(f"Unsupported Virtual Console icon mode: {icon_mode}")

    frame = Image.frombytes(
        "RGB", smdh_format.ICON_LARGE_DIMENSIONS, donor.icon_large
    ).convert("RGBA")
    inset = 4
    interior_size = frame.width - inset * 2
    if interior_size <= 0:
        raise ValueError("Donor SMDH icon is too small for its retail frame.")
    interior = prepare_artwork_for_viewport(source, (interior_size, interior_size), ICON_LAYOUT)
    result = frame.copy()
    result.alpha_composite(interior, (inset, inset))
    return _png(result)
