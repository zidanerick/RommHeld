from __future__ import annotations

import hashlib
from pathlib import Path

from agbcia.banner.image import ImageSource
from agbcia.gba.footer import extract_logo
from agbcia.inject.pipeline import InjectionRequest, inject


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
    return extract_logo(read_asset(donor_cia), read_asset(boot9))


def build_native_gba_cia(
    rom: bytes,
    artwork: ImageSource,
    *,
    boot_logo: bytes,
    title_id: bytes,
    title_name: str,
    long_title: str | None = None,
    publisher: str = "Homebrew",
    donor_banner: bytes | None = None,
    title_version: int = 0,
) -> bytes:
    """Build an installable GBA CIA that boots through AGB_FIRM."""
    request = InjectionRequest(
        mode="native",
        rom=rom,
        title_id=title_id,
        title_name=title_name[:128],
        icon_image=artwork,
        banner_image=artwork,
        long_title=(long_title or title_name)[:128],
        publisher=publisher[:128],
        boot_logo=boot_logo,
        donor_banner=donor_banner,
        title_version=title_version,
    )
    result = inject(request)
    return result.cia
