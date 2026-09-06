from __future__ import annotations

from PIL import Image

from .vc_presentation import badge_texture_names, presentation_profile


_CBMD_HEADER_SIZE = 0x88
_CBMD_SLOT_COUNT = 14
_CBMD_SLOT_TABLE = 0x08
_CBMD_CWAV_OFFSET = 0x84


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


def _encode_l4_tiled(image: Image.Image, width: int, height: int) -> bytes:
    """Encode a grayscale image into Nintendo/PICA200 tiled L4."""
    try:
        from agbcia.formats.pica_texture import tile_offset
    except ImportError as exc:
        raise RuntimeError("Virtual Console donor banner patching requires agbcia.") from exc

    if width <= 0 or height <= 0 or (width * height) % 2:
        raise ValueError(
            f"L4 texture dimensions must contain an even number of texels, got {width}x{height}."
        )
    source = image.convert("L")
    if source.size != (width, height):
        source = source.resize((width, height), Image.Resampling.LANCZOS)

    out = bytearray(width * height // 2)
    pixels = source.load()
    for y in range(height):
        for x in range(width):
            texel = tile_offset(x, y, width)
            nibble = min(0x0F, (int(pixels[x, y]) + 8) // 17)
            byte_index = texel >> 1
            if texel & 1:
                out[byte_index] = (out[byte_index] & 0x0F) | (nibble << 4)
            else:
                out[byte_index] = (out[byte_index] & 0xF0) | nibble
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
        elif texture.hw_format == 10:  # L4
            chunks.append(_encode_l4_tiled(resized, width, height))
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


def _patch_image_if_present(
    cgfx_bytes: bytes,
    texture_name: str,
    image_source,
    *,
    expected_size: tuple[int, int] | None = None,
) -> tuple[bytes, bool]:
    try:
        from agbcia.exceptions import InvalidAssetError
        from agbcia.formats import cgfx
    except ImportError as exc:
        raise RuntimeError("Virtual Console donor banner patching requires agbcia.") from exc
    try:
        texture = cgfx.find_texture(cgfx_bytes, texture_name)
    except InvalidAssetError:
        return cgfx_bytes, False
    if expected_size is not None and (texture.width, texture.height) != expected_size:
        # Nintendo sometimes reuses a texture name for unrelated material. The
        # Renegade common scene has an 8x8 all-white L4 COMMON2, while the real
        # visible title plates are 256x64 LA8 COMMON2 textures in language
        # scenes. Leave same-name textures with the wrong geometry untouched.
        return cgfx_bytes, False
    return _patch_image(cgfx_bytes, texture_name, image_source), True


def _donor_slots(donor_banner: bytes) -> list[tuple[int, bytes]]:
    try:
        from agbcia.formats import lz11
    except ImportError as exc:
        raise RuntimeError("Virtual Console donor banner patching requires agbcia.") from exc
    if len(donor_banner) < _CBMD_HEADER_SIZE or donor_banner[:4] != b"CBMD":
        raise ValueError("Virtual Console donor banner is not a valid CBMD container.")
    result: list[tuple[int, bytes]] = []
    for slot in range(_CBMD_SLOT_COUNT):
        field = _CBMD_SLOT_TABLE + slot * 4
        offset = int.from_bytes(donor_banner[field : field + 4], "little")
        if offset:
            if offset >= len(donor_banner):
                raise ValueError("Virtual Console donor banner has an invalid CGFX slot offset.")
            result.append((slot, lz11.decompress(donor_banner[offset:])))
    if not result:
        raise ValueError("Virtual Console donor banner has no populated CGFX scenes.")
    return result


def _rebuild_cbmd_preserving_slots(
    donor_banner: bytes,
    scenes: list[tuple[int, bytes]],
) -> bytes:
    """Rebuild a donor CBMD without discarding language scenes or CWAV audio."""
    try:
        from agbcia.formats import lz11
    except ImportError as exc:
        raise RuntimeError("Virtual Console donor banner patching requires agbcia.") from exc

    header = bytearray(donor_banner[:_CBMD_HEADER_SIZE])
    header[_CBMD_SLOT_TABLE : _CBMD_SLOT_TABLE + _CBMD_SLOT_COUNT * 4] = bytes(
        _CBMD_SLOT_COUNT * 4
    )
    header[_CBMD_CWAV_OFFSET : _CBMD_CWAV_OFFSET + 4] = bytes(4)
    body = bytearray()

    for slot, scene in sorted(scenes):
        absolute = _CBMD_HEADER_SIZE + len(body)
        field = _CBMD_SLOT_TABLE + slot * 4
        header[field : field + 4] = absolute.to_bytes(4, "little")
        body += lz11.compress(scene)

    donor_cwav_offset = int.from_bytes(
        donor_banner[_CBMD_CWAV_OFFSET : _CBMD_CWAV_OFFSET + 4], "little"
    )
    if donor_cwav_offset:
        if not (_CBMD_HEADER_SIZE <= donor_cwav_offset <= len(donor_banner)):
            raise ValueError("Virtual Console donor banner has an invalid CWAV offset.")
        while (_CBMD_HEADER_SIZE + len(body)) % 0x10:
            body.append(0)
        new_cwav_offset = _CBMD_HEADER_SIZE + len(body)
        header[_CBMD_CWAV_OFFSET : _CBMD_CWAV_OFFSET + 4] = new_cwav_offset.to_bytes(
            4, "little"
        )
        body += donor_banner[donor_cwav_offset:]

    rebuilt = bytes(header) + bytes(body)
    for slot, _ in scenes:
        field = _CBMD_SLOT_TABLE + slot * 4
        if int.from_bytes(rebuilt[field : field + 4], "little") == 0:
            raise ValueError(f"Rebuilt VC banner lost donor language slot {slot}.")
    return rebuilt


def patch_official_vc_banner(
    donor_banner: bytes,
    front_artwork,
    family: str,
    *,
    badge_image=None,
) -> bytes:
    """Patch game-facing textures while preserving the full retail CBMD."""
    profile = presentation_profile(family)
    badge_names = badge_texture_names(profile)
    if badge_names and badge_image is None:
        raise ValueError(f"{family.upper()} donor presentation requires a generated title badge.")
    if not badge_names and badge_image is not None:
        raise ValueError(f"{family.upper()} donor presentation has no separate badge texture.")

    patched_scenes: list[tuple[int, bytes]] = []
    artwork_hits = 0
    badge_hits = 0
    for slot, scene in _donor_slots(donor_banner):
        patched, hit = _patch_image_if_present(scene, profile.artwork_texture, front_artwork)
        artwork_hits += int(hit)
        if badge_names:
            for badge_name in badge_names:
                patched, hit = _patch_image_if_present(
                    patched,
                    badge_name,
                    badge_image,
                    expected_size=profile.badge_size,
                )
                badge_hits += int(hit)
        patched_scenes.append((slot, patched))

    if artwork_hits == 0:
        raise ValueError(
            f"{family.upper()} donor banner has no {profile.artwork_texture!r} artwork texture."
        )
    if badge_names and badge_hits == 0:
        raise ValueError(
            f"{family.upper()} donor banner has no usable {profile.badge_size or ''} "
            f"title-plaque texture from {badge_names!r}."
        )

    return _rebuild_cbmd_preserving_slots(donor_banner, patched_scenes)
