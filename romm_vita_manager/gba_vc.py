from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from agbcia.banner.image import ImageSource

_MAX_GBA_ROM_SIZE = 0x2000000
_CIA_HEADER_SIZE = 0x2020
_COMMON_KEYS = {
    0: bytes.fromhex("64C5FD55DD3AD988325BAAEC5243DB98"),
    1: bytes.fromhex("4AAA3D0E27D4D728D0B1B433F0F9CBC8"),
}
_TMD_SIGNATURE_SIZES = {
    0x00010000: 0x23C,
    0x00010001: 0x13C,
    0x00010002: 0x7C,
    0x00010003: 0x23C,
    0x00010004: 0x13C,
    0x00010005: 0x7C,
}


def _require_agbcia():
    try:
        from agbcia.inject.pipeline import InjectionRequest, inject
    except ImportError as exc:
        raise RuntimeError(
            "Native GBA packaging requires the 'agbcia' package. "
            "Install it with: python -m pip install -r requirements.txt"
        ) from exc
    return InjectionRequest, inject


def _require_agbcia_donor_tools():
    try:
        from agbcia.crypto import aes_ctr, ncch_keys
        from agbcia.formats import exefs as exefs_format
        from agbcia.formats import ncch as ncch_format
    except ImportError as exc:
        raise RuntimeError(
            "GBA donor extraction requires the 'agbcia' package and its crypto dependencies."
        ) from exc
    return aes_ctr, ncch_keys, exefs_format, ncch_format


def native_title_id_for_romm_id(romm_id: int) -> bytes:
    """Return a stable 3DS GBA VC-range title ID for a RomM ROM ID."""
    if romm_id < 0:
        raise ValueError("RomM ROM ID must be non-negative.")
    digest = hashlib.sha256(str(romm_id).encode("ascii")).digest()
    unique = int.from_bytes(digest[:2], "big") & 0x0FFF
    return bytes.fromhex(f"0004000000F{unique:03X}00")


def read_asset(path: Path) -> bytes:
    path = path.expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Asset does not exist: {path}")
    return path.read_bytes()


def _align64(value: int) -> int:
    return (value + 63) & ~63


def _primary_ncch_from_cia(donor_cia: bytes) -> bytes:
    """Return the primary application NCCH from a retail/piratelegit CIA."""
    try:
        from Crypto.Cipher import AES
    except ImportError as exc:
        raise RuntimeError("CIA donor extraction requires pycryptodome.") from exc

    if len(donor_cia) < _CIA_HEADER_SIZE:
        raise ValueError("Donor is too small to be a valid CIA.")
    header_size = int.from_bytes(donor_cia[0:4], "little")
    if header_size != _CIA_HEADER_SIZE:
        raise ValueError(f"Unexpected CIA header size: {header_size:#x}")
    cert_size = int.from_bytes(donor_cia[0x08:0x0C], "little")
    ticket_size = int.from_bytes(donor_cia[0x0C:0x10], "little")
    tmd_size = int.from_bytes(donor_cia[0x10:0x14], "little")

    cert_offset = _align64(header_size)
    ticket_offset = _align64(cert_offset + cert_size)
    tmd_offset = _align64(ticket_offset + ticket_size)
    content_offset = _align64(tmd_offset + tmd_size)
    if content_offset >= len(donor_cia):
        raise ValueError("CIA content section is missing.")

    ticket = donor_cia[ticket_offset : ticket_offset + ticket_size]
    if len(ticket) < 0x1F2:
        raise ValueError("CIA ticket is truncated.")
    encrypted_title_key = ticket[0x1BF:0x1CF]
    title_id = ticket[0x1DC:0x1E4]
    common_key_index = ticket[0x1F1]
    try:
        common_key = _COMMON_KEYS[common_key_index]
    except KeyError:
        raise ValueError(f"Unsupported CIA common-key index: {common_key_index}") from None
    title_key = AES.new(common_key, AES.MODE_CBC, iv=title_id + bytes(8)).decrypt(
        encrypted_title_key
    )

    signature_type = int.from_bytes(donor_cia[tmd_offset : tmd_offset + 4], "big")
    signature_size = _TMD_SIGNATURE_SIZES.get(signature_type)
    if signature_size is None:
        raise ValueError(f"Unsupported TMD signature type: {signature_type:#x}")
    tmd_header = tmd_offset + 4 + signature_size
    content_count = int.from_bytes(
        donor_cia[tmd_header + 0x9E : tmd_header + 0xA0], "big"
    )
    chunk_table = tmd_header + 0xC4 + 64 * 0x24
    if content_count < 1:
        raise ValueError("CIA contains no application content.")

    row = donor_cia[chunk_table : chunk_table + 0x30]
    if len(row) < 0x30:
        raise ValueError("CIA TMD content table is truncated.")
    content_index = int.from_bytes(row[4:6], "big")
    content_type = int.from_bytes(row[6:8], "big")
    content_size = int.from_bytes(row[8:16], "big")
    raw = donor_cia[content_offset : content_offset + content_size]
    if len(raw) != content_size:
        raise ValueError("CIA primary content is truncated.")

    if raw[0x100:0x104] == b"NCCH":
        return raw
    if not (content_type & 0x1):
        raise ValueError("CIA primary content is not an NCCH and is not marked encrypted.")
    if content_size % 16:
        raise ValueError("Encrypted CIA content is not AES block aligned.")
    iv = content_index.to_bytes(2, "big") + bytes(14)
    ncch = AES.new(title_key, AES.MODE_CBC, iv=iv).decrypt(raw)
    if ncch[0x100:0x104] != b"NCCH":
        raise ValueError("Unable to decrypt the donor CIA primary NCCH.")
    return ncch


def _extract_ncch_exefs_entry(ncch: bytes, boot9: bytes, name: str) -> bytes:
    aes_ctr, ncch_keys, exefs_format, ncch_format = _require_agbcia_donor_tools()
    info = ncch_format.parse(ncch)
    if info.exefs is None:
        raise ValueError("Donor NCCH has no ExeFS.")
    exefs_bytes = ncch[info.exefs.offset : info.exefs.offset + info.exefs.size]
    header = exefs_bytes[: exefs_format.HEADER_SIZE]
    if not info.no_crypto:
        main_key = ncch_keys.main_key(boot9, info.key_y)
        header = aes_ctr.decrypt_region(
            main_key, info.title_id, ncch_format.SECTION_EXEFS, header
        )
    entries = exefs_format.parse_header(header)
    if name not in entries:
        raise ValueError(f"Donor ExeFS does not contain {name!r}.")
    entry = entries[name]
    file_offset = exefs_format.HEADER_SIZE + entry.offset
    data = exefs_bytes[file_offset : file_offset + entry.size]
    if info.no_crypto:
        return data

    if name in {"icon", "banner"}:
        key = ncch_keys.main_key(boot9, info.key_y)
    else:
        key = ncch_keys.extra_key(boot9, info.key_y, info.crypto_method)
    block_offset = file_offset // aes_ctr.BLOCK_SIZE
    return aes_ctr.decrypt_region(
        key,
        info.title_id,
        ncch_format.SECTION_EXEFS,
        data,
        block_offset=block_offset,
    )


def extract_native_boot_logo(donor_cia: Path, boot9: Path) -> bytes:
    """Extract the AGB_FIRM boot logo from an encrypted or plaintext donor CIA."""
    donor = read_asset(donor_cia)
    keys = read_asset(boot9)
    ncch = _primary_ncch_from_cia(donor)
    _, _, _, ncch_format = _require_agbcia_donor_tools()
    info = ncch_format.parse(ncch)
    if info.logo is not None:
        return ncch[info.logo.offset : info.logo.offset + info.logo.size]
    return _extract_ncch_exefs_entry(ncch, keys, "logo")


def extract_native_donor_banner(donor_cia: Path, boot9: Path) -> bytes:
    """Extract the real animated GBA VC ExeFS banner from a donor CIA."""
    donor = read_asset(donor_cia)
    keys = read_asset(boot9)
    ncch = _primary_ncch_from_cia(donor)
    return _extract_ncch_exefs_entry(ncch, keys, "banner")


def prepare_gba_rom(rom: bytes) -> bytes:
    """Return a raw GBA ROM, transparently extracting a .gba from ZIP input."""
    if len(rom) > _MAX_GBA_ROM_SIZE:
        try:
            is_zip = zipfile.is_zipfile(io.BytesIO(rom))
        except OSError:
            is_zip = False
        if not is_zip:
            raise ValueError("GBA ROM is larger than the 32 MiB maximum supported size.")

    try:
        archive = zipfile.ZipFile(io.BytesIO(rom))
    except (OSError, zipfile.BadZipFile):
        return rom

    with archive:
        candidates = [
            info
            for info in archive.infolist()
            if not info.is_dir() and info.filename.lower().endswith(".gba")
        ]
        if not candidates:
            raise ValueError("ZIP archive does not contain a .gba ROM.")
        candidates.sort(key=lambda info: (info.filename.count("/"), info.filename.lower()))
        selected = candidates[0]
        if selected.file_size > _MAX_GBA_ROM_SIZE:
            raise ValueError(
                "The GBA ROM inside the ZIP is larger than the 32 MiB maximum supported size."
            )
        return archive.read(selected)


def prepare_vc_icon_artwork(artwork: bytes, *, canvas_size: int = 256) -> bytes:
    """Fit full box artwork into a square HOME Menu icon without destructive cropping."""
    image = Image.open(io.BytesIO(artwork)).convert("RGB")
    if image.width < 1 or image.height < 1:
        raise ValueError("Artwork has invalid dimensions.")

    sample = image.resize((16, 16), Image.Resampling.BILINEAR)
    edge_pixels: list[tuple[int, int, int]] = []
    for x in range(sample.width):
        edge_pixels.append(sample.getpixel((x, 0)))
        edge_pixels.append(sample.getpixel((x, sample.height - 1)))
    for y in range(1, sample.height - 1):
        edge_pixels.append(sample.getpixel((0, y)))
        edge_pixels.append(sample.getpixel((sample.width - 1, y)))
    count = max(1, len(edge_pixels))
    background = tuple(
        sum(pixel[channel] for pixel in edge_pixels) // count for channel in range(3)
    )

    margin = max(10, canvas_size // 16)
    available = canvas_size - margin * 2
    scale = min(available / image.width, available / image.height)
    fitted = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGB", (canvas_size, canvas_size), background)
    canvas.paste(
        fitted,
        ((canvas_size - fitted.width) // 2, (canvas_size - fitted.height) // 2),
    )
    output = io.BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()


def prepare_vc_title_badge(
    title_name: str,
    *,
    width: int = 512,
    height: int = 128,
) -> bytes:
    """Render the per-title text texture displayed below the rotating VC box."""
    title = " ".join(title_name.split()).strip()[:128]
    if not title:
        raise ValueError("Virtual Console title badge requires a non-empty title.")

    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(canvas)
    margin_x = max(8, width // 32)
    margin_y = max(6, height // 16)
    max_width = width - margin_x * 2
    max_height = height - margin_y * 2

    chosen_font = None
    chosen_lines = [title]
    for size in range(max(18, height // 3), 9, -2):
        try:
            font = ImageFont.load_default(size=size)
        except TypeError:
            font = ImageFont.load_default()

        words = title.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), candidate, font=font, stroke_width=1)
            if current and bbox[2] - bbox[0] > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)

        if len(lines) > 2:
            continue
        line_boxes = [draw.textbbox((0, 0), line, font=font, stroke_width=1) for line in lines]
        line_heights = [box[3] - box[1] for box in line_boxes]
        total_height = sum(line_heights) + max(0, len(lines) - 1) * 4
        if all((box[2] - box[0]) <= max_width for box in line_boxes) and total_height <= max_height:
            chosen_font = font
            chosen_lines = lines
            break

    if chosen_font is None:
        chosen_font = ImageFont.load_default()

    boxes = [draw.textbbox((0, 0), line, font=chosen_font, stroke_width=1) for line in chosen_lines]
    heights = [box[3] - box[1] for box in boxes]
    total_height = sum(heights) + max(0, len(chosen_lines) - 1) * 4
    y = (height - total_height) // 2
    for line, box, line_height in zip(chosen_lines, boxes, heights):
        line_width = box[2] - box[0]
        x = (width - line_width) // 2
        draw.text(
            (x, y),
            line,
            font=chosen_font,
            fill=(255, 255, 255, 255),
            stroke_width=1,
            stroke_fill=(0, 0, 0, 210),
        )
        y += line_height + 4

    output = io.BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()


def build_native_gba_cia(
    rom: bytes,
    artwork: "ImageSource",
    *,
    boot_logo: bytes,
    title_id: bytes,
    title_name: str,
    long_title: str | None = None,
    publisher: str = "",
    donor_banner: bytes | None = None,
    title_version: int = 0,
) -> bytes:
    """Build an installable GBA CIA that boots through AGB_FIRM.

    ``publisher`` is intentionally blank by default. Callers should pass real
    game metadata when available instead of stamping generated titles with a
    generic "Homebrew" marker.
    """
    if not boot_logo:
        raise ValueError(
            "Native GBA packaging requires an extracted AGB_FIRM boot logo. "
            "Configure a valid boot-logo asset before building the CIA."
        )

    InjectionRequest, inject = _require_agbcia()
    rom = prepare_gba_rom(rom)
    icon_image = prepare_vc_icon_artwork(artwork) if isinstance(artwork, bytes) else artwork
    bottom_badge_image = prepare_vc_title_badge(title_name) if donor_banner is not None else None
    request = InjectionRequest(
        mode="native",
        rom=rom,
        title_id=title_id,
        title_name=title_name[:128],
        icon_image=icon_image,
        banner_image=artwork,
        long_title=(long_title or title_name)[:128],
        publisher=publisher[:128],
        boot_logo=boot_logo,
        donor_banner=donor_banner,
        bottom_badge_image=bottom_badge_image,
        title_version=title_version,
    )
    result = inject(request)
    return result.cia
