from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageOps


@dataclass(frozen=True, slots=True)
class ArtworkLayout:
    """How source artwork is fitted into a Nintendo VC presentation viewport.

    ``platform_chrome`` removes the family branding that belongs to a retail
    box scan but not to Nintendo's small VC label texture.  The crop is only
    applied to portrait artwork, which is the normal shape of box-front scans;
    square/title-screen artwork is left untouched.
    """

    mode: str
    padding: int = 0
    centering: tuple[float, float] = (0.5, 0.5)
    trim_uniform_border: bool = True
    platform_chrome: str | None = None


# Nintendo's retail donor textures do not display a complete retail box front.
# They use a compact game-art label inside the family-specific frame.  RomM
# commonly supplies box-front artwork, so remove the platform-only chrome and
# then crop to fill the donor's measured label viewport rather than shrinking
# the complete portrait cover into it.
GBA_BANNER_LAYOUT = ArtworkLayout(
    "cover",
    padding=3,
    centering=(0.5, 0.5),
    platform_chrome="gba_top",
)
GB_LABEL_LAYOUT = ArtworkLayout(
    "cover",
    padding=1,
    centering=(0.52, 0.48),
    platform_chrome="gb_left",
)
GBC_LABEL_LAYOUT = ArtworkLayout(
    "cover",
    padding=1,
    centering=(0.54, 0.48),
    platform_chrome="gbc_left",
)
ICON_LAYOUT = ArtworkLayout("cover", padding=1, centering=(0.5, 0.45))


def _edge_background(image: Image.Image) -> tuple[int, int, int]:
    sample = image.convert("RGB").resize((16, 16), Image.Resampling.BILINEAR)
    pixels: list[tuple[int, int, int]] = []
    for x in range(sample.width):
        pixels.append(sample.getpixel((x, 0)))
        pixels.append(sample.getpixel((x, sample.height - 1)))
    for y in range(1, sample.height - 1):
        pixels.append(sample.getpixel((0, y)))
        pixels.append(sample.getpixel((sample.width - 1, y)))
    count = max(1, len(pixels))
    return tuple(sum(pixel[channel] for pixel in pixels) // count for channel in range(3))


def _uniform_border_bbox(
    image: Image.Image,
    *,
    threshold: int = 22,
    max_trim_ratio: float = 0.18,
) -> tuple[int, int, int, int]:
    """Return a conservative crop for flat scanner/box-art margins.

    The reference colour comes from the four corners. Only pixels that differ
    materially from that colour are considered content, and each edge is
    capped to a modest fraction of the source size so a legitimate background
    cannot accidentally be stripped away.
    """
    source = image.convert("RGB")
    width, height = source.size
    if width < 8 or height < 8:
        return (0, 0, width, height)

    corners = (
        source.getpixel((0, 0)),
        source.getpixel((width - 1, 0)),
        source.getpixel((0, height - 1)),
        source.getpixel((width - 1, height - 1)),
    )
    reference = tuple(sum(pixel[channel] for pixel in corners) // 4 for channel in range(3))

    # Scan a bounded working copy so large RomM cover images do not make banner
    # generation unnecessarily expensive.
    scale = min(1.0, 320 / max(width, height))
    if scale < 1.0:
        work = source.resize(
            (max(1, round(width * scale)), max(1, round(height * scale))),
            Image.Resampling.BILINEAR,
        )
    else:
        work = source
    work_width, work_height = work.size

    left, top, right, bottom = work_width, work_height, -1, -1
    for y in range(work_height):
        for x in range(work_width):
            pixel = work.getpixel((x, y))
            if max(abs(pixel[channel] - reference[channel]) for channel in range(3)) > threshold:
                left = min(left, x)
                top = min(top, y)
                right = max(right, x)
                bottom = max(bottom, y)

    if right < left or bottom < top:
        return (0, 0, width, height)

    inverse = 1.0 / scale
    candidate = (
        max(0, round(left * inverse)),
        max(0, round(top * inverse)),
        min(width, round((right + 1) * inverse)),
        min(height, round((bottom + 1) * inverse)),
    )
    max_x = round(width * max_trim_ratio)
    max_y = round(height * max_trim_ratio)
    clamped = (
        min(candidate[0], max_x),
        min(candidate[1], max_y),
        max(candidate[2], width - max_x),
        max(candidate[3], height - max_y),
    )
    if clamped[2] <= clamped[0] or clamped[3] <= clamped[1]:
        return (0, 0, width, height)
    return clamped


def _strip_platform_chrome(image: Image.Image, kind: str | None) -> Image.Image:
    """Remove box-only platform branding before adapting art to a VC label.

    The supplied official donors show that Nintendo's VC textures contain game
    artwork, not the full retail box-front chrome.  Typical RomM box scans use
    a horizontal ``GAME BOY ADVANCE`` header or a vertical GB/GBC family strip.
    Removing those areas before the final cover crop prevents the platform logo
    from consuming a large part of the tiny 128x128/70x74 VC viewport.

    This is deliberately conservative: only clearly portrait source images are
    altered.  Square artwork, title screens and already-prepared labels pass
    through unchanged.
    """
    if not kind:
        return image
    source = image.convert("RGBA")
    width, height = source.size
    if width < 16 or height < 16 or height / width < 1.12:
        return source

    if kind == "gba_top":
        # Retail GBA covers reserve roughly the top eighth for the platform
        # masthead.  The remaining art is then cropped to Nintendo's square VC
        # label, which also naturally removes most bottom legal-copy space.
        top = min(height - 1, max(1, round(height * 0.13)))
        return source.crop((0, top, width, height))
    if kind == "gb_left":
        # Original Game Boy boxes commonly carry a narrow vertical GAME BOY
        # family strip on the left edge.
        left = min(width - 1, max(1, round(width * 0.12)))
        return source.crop((left, 0, width, height))
    if kind == "gbc_left":
        # Game Boy Color boxes use a slightly wider black GAME BOY COLOR strip.
        left = min(width - 1, max(1, round(width * 0.15)))
        return source.crop((left, 0, width, height))
    raise ValueError(f"Unsupported VC platform-chrome crop: {kind}")


def prepare_artwork_for_viewport(
    artwork: Image.Image,
    size: tuple[int, int],
    layout: ArtworkLayout,
) -> Image.Image:
    """Fit artwork into an exact VC viewport without touching its outer frame."""
    width, height = size
    if width <= 0 or height <= 0:
        raise ValueError("Virtual Console artwork viewport must be positive.")
    padding = max(0, min(layout.padding, (min(width, height) - 1) // 2))
    inner_size = (max(1, width - padding * 2), max(1, height - padding * 2))

    source = artwork.convert("RGBA")
    source = _strip_platform_chrome(source, layout.platform_chrome)
    if layout.trim_uniform_border:
        source = source.crop(_uniform_border_bbox(source))

    background = _edge_background(source)
    canvas = Image.new("RGBA", (width, height), (*background, 255))

    if layout.mode == "cover":
        fitted = ImageOps.fit(
            source,
            inner_size,
            Image.Resampling.LANCZOS,
            centering=layout.centering,
        )
    elif layout.mode == "contain":
        fitted = ImageOps.contain(source, inner_size, Image.Resampling.LANCZOS)
    else:
        raise ValueError(f"Unsupported VC artwork layout mode: {layout.mode}")

    x = padding + (inner_size[0] - fitted.width) // 2
    y = padding + (inner_size[1] - fitted.height) // 2
    canvas.alpha_composite(fitted, (x, y))
    return canvas
