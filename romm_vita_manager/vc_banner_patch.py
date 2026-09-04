from __future__ import annotations

from PIL import Image

from .vc_presentation import presentation_profile


def _encode_rgb565_tiled(image: Image.Image, width: int, height: int) -> bytes:
    """Encode row-major RGB artwork into the PICA200 tiled RGB565 format."""
    try:
        from agbcia.formats.pica_texture import tile_offset
    except ImportError as exc:
        raise RuntimeError("Virtual Console donor banner patching requires agbcia.") from exc

    source = image.convert("RGB")
    if source.size != (width, height):
        source = source.resize((width, height), Image.Resampling.LANCZOS)
    out = bytearray(width * height * 2)
    pixels = source.load()
    for y in range(height):
        for x in range(width):
            red, green, blue = pixels[x, y]
            value = ((red >> 3) << 11) | ((green >> 2) << 5) | (blue >> 3)
            offset = tile_offset(x, y, width) * 2
            out[offset : offset + 2] = value.to_bytes(2, "little")
    return bytes(out)


def _encode_texture_mips(image: Image.Image, texture) -> bytes:
    try:
        from agbcia.formats import pica_texture
    except ImportError as exc:
        raise RuntimeError("Virtual Console donor banner patching requires agbcia.") from exc

    chunks: list[bytes] = []
    levels = max(1, int(texture.mipmap_count))
    for level in range(levels):
        width = max(1, texture.width >> level)
        height = max(1, texture.height >> level)
        resized = image.resize((width, height), Image.Resampling.LANCZOS)
        if texture.hw_format == 0:  # RGBA8
            rgba = resized.convert("RGBA")
            chunks.append(pica_texture.encode_rgba8(rgba.tobytes(), width, height))
        elif texture.hw_format == 3:  # RGB565
            chunks.append(_encode_rgb565_tiled(resized, width, height))
        elif texture.hw_format == 5:  # LA8
            la = resized.convert("LA")
            chunks.append(pica_texture.encode_la8(la.tobytes(), width, height))
        else:
            raise ValueError(
                f"Unsupported game-facing donor texture format {texture.hw_format} "
                f"for {texture.name!r}."
            )
    return b"".join(chunks)


def _patch_image(cgfx_bytes: bytes, texture_name: str, image_source) -> bytes:
    try:
        from agbcia.banner.image import load_image
        from agbcia.formats import cgfx
    except ImportError as exc:
        raise RuntimeError("Virtual Console donor banner patching requires agbcia.") from exc

    texture = cgfx.find_texture(cgfx_bytes, texture_name)
    image = load_image(image_source)
    encoded = _encode_texture_mips(image, texture)
    if len(encoded) != texture.raw_buffer_length:
        raise ValueError(
            f"Encoded {texture_name} mip chain is {len(encoded)} bytes; "
            f"the donor requires {texture.raw_buffer_length}."
        )
    return cgfx.patch_texture(cgfx_bytes, texture, encoded)


def patch_official_vc_banner(
    donor_banner: bytes,
    front_artwork,
    family: str,
    *,
    badge_image=None,
) -> bytes:
    """Patch only the game-specific textures in a locally supplied VC banner.

    This is intentionally profile-driven rather than agbcia's GBA-specific
    ``patch_donor_banner`` helper. NES uses RGB565 COMMON1, SNES uses RGBA8
    COMMON1, and Game Gear uses RGB565 COMMON2 while COMMON3 is its hardware
    shell. All mesh, animation, material and unrelated system textures remain
    byte-identical in the decompressed donor CGFX.
    """
    try:
        from agbcia.formats import cbmd, lz11
    except ImportError as exc:
        raise RuntimeError("Virtual Console donor banner patching requires agbcia.") from exc

    profile = presentation_profile(family)
    compressed = cbmd.extract_common_cgfx(donor_banner)
    donor_cgfx = lz11.decompress(compressed)
    patched = _patch_image(donor_cgfx, profile.artwork_texture, front_artwork)

    if profile.badge_texture is not None:
        if badge_image is None:
            raise ValueError(
                f"{family.upper()} donor presentation requires a generated title badge."
            )
        patched = _patch_image(patched, profile.badge_texture, badge_image)
    elif badge_image is not None:
        raise ValueError(f"{family.upper()} donor presentation has no separate badge texture.")

    # Rebuild only the CBMD container around the patched donor scene. agbcia's
    # builder LZ11-compresses the CGFX and supplies the standard silent banner
    # CWAV, matching RommHeld's existing donor-backed VC behavior.
    return cbmd.build(cgfx=patched, cwav=None)
