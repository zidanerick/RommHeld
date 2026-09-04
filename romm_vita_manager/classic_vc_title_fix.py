from __future__ import annotations

import hashlib


# 3DS normal application Unique IDs occupy 0x000300..0x0F7FFF. Keep
# RommHeld-generated classic VC titles in a private-looking high part of that
# normal application range, with title variation byte 0x00.
_CLASSIC_UID_BASE = 0x0E0000
_CLASSIC_UID_MASK = 0x00FFFF


def hardware_safe_classic_title_id(romm_id: int, family: str) -> bytes:
    """Return a stable normal-application title ID for a GB/GBC inject.

    TitleID-low is laid out as ``UUUUUUVV``: a 24-bit Unique ID followed by
    an 8-bit variation. The first classic VC implementation accidentally used
    a 28-bit value directly as TitleID-low, yielding Unique IDs around
    0xE00000, outside the normal application range. On hardware that can make
    HOME Menu fail title lookup at launch with ErrDisp 0xC8804478.
    """
    family = family.lower()
    if family not in {"gb", "gbc"}:
        raise ValueError(f"Unsupported classic VC family: {family}")
    if romm_id < 0:
        raise ValueError("RomM ROM ID must be non-negative.")

    digest = hashlib.sha256(f"{family}:{romm_id}".encode("ascii")).digest()
    unique_id = _CLASSIC_UID_BASE | (int.from_bytes(digest[:2], "big") & _CLASSIC_UID_MASK)
    title_low = (unique_id << 8) | 0x00
    return bytes.fromhex(f"00040000{title_low:08X}")


def install() -> None:
    """Install the corrected title-ID generator into the classic VC module."""
    from . import classic_vc

    classic_vc.classic_title_id_for_romm_id = hardware_safe_classic_title_id
