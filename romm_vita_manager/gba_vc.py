from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from .gba_boot_logo import bundled_boot_logo

if TYPE_CHECKING:
    from agbcia.banner.image import ImageSource

_MAX_GBA_ROM_SIZE = 0x2000000


def _require_agbcia():
    try:
        from agbcia.gba.footer import extract_logo
        from agbcia.inject.pipeline import InjectionRequest, inject
    except ImportError as exc:
        raise RuntimeError(
            "Native GBA packaging requires the 'agbcia' package. "
            "Install it with: python -m pip install -r requirements.txt"
        ) from exc
    return extract_logo, InjectionRequest, inject


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


def extract_native_boot_logo(donor_cia: Path, boot9: Path) -> bytes:
    """Extract the AGB_FIRM boot logo from a donor CIA the user owns."""
    extract_logo, _, _ = _require_agbcia()
    return extract_logo(read_asset(donor_cia), read_asset(boot9))


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
            info for info in archive.infolist()
            if not info.is_dir() and info.filename.lower().endswith(".gba")
        ]
        if not candidates:
            raise ValueError("ZIP archive does not contain a .gba ROM.")
        candidates.sort(key=lambda info: (info.filename.count("/"), info.filename.lower()))
        selected = candidates[0]
        if selected.file_size > _MAX_GBA_ROM_SIZE:
            raise ValueError("The GBA ROM inside the ZIP is larger than the 32 MiB maximum supported size.")
        return archive.read(selected)


def build_native_gba_cia(
    rom: bytes,
    artwork: "ImageSource",
    *,
    boot_logo: bytes | None = None,
    title_id: bytes,
    title_name: str,
    long_title: str | None = None,
    publisher: str = "Homebrew",
    donor_banner: bytes | None = None,
    title_version: int = 0,
) -> bytes:
    """Build an installable GBA CIA that boots through AGB_FIRM.

    When no boot logo is supplied, use RommHeld's bundled original fallback
    so normal packaging never requires a donor CIA or boot9 dump.
    ZIP archives containing a .gba are accepted transparently.
    """
    _, InjectionRequest, inject = _require_agbcia()
    rom = prepare_gba_rom(rom)
    request = InjectionRequest(
        mode="native",
        rom=rom,
        title_id=title_id,
        title_name=title_name[:128],
        icon_image=artwork,
        banner_image=artwork,
        long_title=(long_title or title_name)[:128],
        publisher=publisher[:128],
        boot_logo=boot_logo if boot_logo is not None else bundled_boot_logo(),
        donor_banner=donor_banner,
        title_version=title_version,
    )
    result = inject(request)
    return result.cia
