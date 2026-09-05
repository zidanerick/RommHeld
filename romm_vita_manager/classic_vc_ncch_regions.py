from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


_MEDIA_UNIT = 0x200
_NCCH_HEADER_SIZE = 0x200
_EXHEADER_REGION_SIZE = 0x800
_INSERT_OFFSET = _NCCH_HEADER_SIZE + _EXHEADER_REGION_SIZE
_LOGO_HASH_OFFSET = 0x130
_PLAIN_OFFSET_FIELD = 0x190
_PLAIN_SIZE_FIELD = 0x194
_LOGO_OFFSET_FIELD = 0x198
_LOGO_SIZE_FIELD = 0x19C
_EXEFS_OFFSET_FIELD = 0x1A0
_ROMFS_OFFSET_FIELD = 0x1B0
_CONTENT_SIZE_FIELD = 0x104
_SUPPORTED = {"gb", "gbc", "nes", "gamegear", "snes"}


@dataclass(frozen=True, slots=True)
class NcchAuxiliaryRegions:
    plain: bytes = b""
    logo: bytes = b""


def _read_units(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little")


def _slice_media_region(data: bytes, offset_field: int, size_field: int, name: str) -> bytes:
    offset_units = _read_units(data, offset_field)
    size_units = _read_units(data, size_field)
    if offset_units == 0 and size_units == 0:
        return b""
    if offset_units == 0 or size_units == 0:
        raise ValueError(f"Donor NCCH has an inconsistent {name} offset/size pair.")
    start = offset_units * _MEDIA_UNIT
    size = size_units * _MEDIA_UNIT
    end = start + size
    if start < _NCCH_HEADER_SIZE or end > len(data):
        raise ValueError(f"Donor NCCH {name} region extends outside the content.")
    return bytes(data[start:end])


def extract_ncch_auxiliary_regions(ncch: bytes) -> NcchAuxiliaryRegions:
    """Extract the plaintext NCCH logo/plain regions from a retail donor.

    SDK 5+ applications may keep the launch logo in the dedicated NCCH logo
    region rather than ExeFS. The plain region normally carries SDK build tags.
    Both regions sit outside the encrypted ExeFS/RomFS data, so preserving the
    user's locally supplied bytes does not require NCCH content decryption.
    """
    if len(ncch) < _INSERT_OFFSET or ncch[0x100:0x104] != b"NCCH":
        raise ValueError("Virtual Console donor does not contain a valid NCCH application.")
    plain = _slice_media_region(ncch, _PLAIN_OFFSET_FIELD, _PLAIN_SIZE_FIELD, "plain")
    logo = _slice_media_region(ncch, _LOGO_OFFSET_FIELD, _LOGO_SIZE_FIELD, "logo")
    if logo and len(logo) != 0x2000:
        raise ValueError(
            f"Retail NCCH launch logo must be 0x2000 bytes, got {len(logo):#x}."
        )
    return NcchAuxiliaryRegions(plain=plain, logo=logo)


def _validate_media_aligned(data: bytes, name: str) -> None:
    if data and len(data) % _MEDIA_UNIT:
        raise ValueError(f"NCCH {name} region must be {_MEDIA_UNIT:#x}-byte aligned.")


def apply_ncch_auxiliary_regions(
    ncch: bytes,
    *,
    plain: bytes = b"",
    logo: bytes = b"",
) -> bytes:
    """Insert donor logo/plain regions into a generated no-crypto NCCH.

    RommHeld's agbcia writer intentionally emits the minimal
    header+exheader+ExeFS+RomFS layout. Retail NES/SNES VC donors instead carry
    a dedicated launch-logo region and several other VC donors carry a plain
    SDK-tag region. This routine restores those optional retail regions while
    leaving ExeFS/RomFS byte-identical and updating only their media-unit
    offsets, the NCCH content size, and the dedicated logo hash.
    """
    plain = bytes(plain)
    logo = bytes(logo)
    _validate_media_aligned(plain, "plain")
    _validate_media_aligned(logo, "logo")
    if logo and len(logo) != 0x2000:
        raise ValueError(f"NCCH launch logo must be exactly 0x2000 bytes, got {len(logo):#x}.")
    if len(ncch) < _INSERT_OFFSET or ncch[0x100:0x104] != b"NCCH":
        raise ValueError("Generated Virtual Console NCCH is invalid.")
    if len(ncch) % _MEDIA_UNIT:
        raise ValueError("Generated Virtual Console NCCH is not media-unit aligned.")

    existing_plain = (_read_units(ncch, _PLAIN_OFFSET_FIELD), _read_units(ncch, _PLAIN_SIZE_FIELD))
    existing_logo = (_read_units(ncch, _LOGO_OFFSET_FIELD), _read_units(ncch, _LOGO_SIZE_FIELD))
    if existing_plain != (0, 0) or existing_logo != (0, 0):
        raise ValueError("Generated NCCH already contains an auxiliary plain/logo region.")

    if not plain and not logo:
        return ncch

    exefs_units = _read_units(ncch, _EXEFS_OFFSET_FIELD)
    if exefs_units * _MEDIA_UNIT != _INSERT_OFFSET:
        raise ValueError(
            "Generated VC NCCH has an unexpected pre-ExeFS layout; refusing to shift regions blindly."
        )

    logo_units = len(logo) // _MEDIA_UNIT
    plain_units = len(plain) // _MEDIA_UNIT
    delta_units = logo_units + plain_units

    rebuilt = bytearray(ncch[:_INSERT_OFFSET] + logo + plain + ncch[_INSERT_OFFSET:])
    header = rebuilt[:_NCCH_HEADER_SIZE]

    if logo:
        header[_LOGO_OFFSET_FIELD : _LOGO_OFFSET_FIELD + 4] = (
            _INSERT_OFFSET // _MEDIA_UNIT
        ).to_bytes(4, "little")
        header[_LOGO_SIZE_FIELD : _LOGO_SIZE_FIELD + 4] = logo_units.to_bytes(4, "little")
        header[_LOGO_HASH_OFFSET : _LOGO_HASH_OFFSET + 0x20] = hashlib.sha256(logo).digest()
    else:
        header[_LOGO_HASH_OFFSET : _LOGO_HASH_OFFSET + 0x20] = bytes(0x20)

    if plain:
        plain_offset_units = (_INSERT_OFFSET // _MEDIA_UNIT) + logo_units
        header[_PLAIN_OFFSET_FIELD : _PLAIN_OFFSET_FIELD + 4] = plain_offset_units.to_bytes(
            4, "little"
        )
        header[_PLAIN_SIZE_FIELD : _PLAIN_SIZE_FIELD + 4] = plain_units.to_bytes(4, "little")

    for field in (_EXEFS_OFFSET_FIELD, _ROMFS_OFFSET_FIELD):
        old = _read_units(ncch, field)
        if old:
            header[field : field + 4] = (old + delta_units).to_bytes(4, "little")

    total_units = len(rebuilt) // _MEDIA_UNIT
    header[_CONTENT_SIZE_FIELD : _CONTENT_SIZE_FIELD + 4] = total_units.to_bytes(4, "little")
    rebuilt[:_NCCH_HEADER_SIZE] = header
    result = bytes(rebuilt)
    validate_applied_ncch_auxiliary_regions(result, plain=plain, logo=logo)
    return result


def validate_applied_ncch_auxiliary_regions(
    ncch: bytes,
    *,
    plain: bytes = b"",
    logo: bytes = b"",
) -> None:
    if len(ncch) % _MEDIA_UNIT or _read_units(ncch, _CONTENT_SIZE_FIELD) != len(ncch) // _MEDIA_UNIT:
        raise ValueError("Final VC NCCH content-size field does not match the serialized content.")
    actual = extract_ncch_auxiliary_regions(ncch)
    if actual.plain != bytes(plain):
        raise ValueError("Final VC NCCH did not preserve the donor plain region.")
    if actual.logo != bytes(logo):
        raise ValueError("Final VC NCCH did not preserve the donor launch-logo region.")
    expected_hash = hashlib.sha256(logo).digest() if logo else bytes(0x20)
    if ncch[_LOGO_HASH_OFFSET : _LOGO_HASH_OFFSET + 0x20] != expected_hash:
        raise ValueError("Final VC NCCH launch-logo hash is invalid.")


def auxiliary_cache_paths(family: str) -> tuple[Path, Path]:
    key = family.strip().lower()
    if key not in _SUPPORTED:
        raise ValueError(f"Unsupported classic VC family: {family}")
    from .config import package_cache_dir

    root = package_cache_dir() / "classic_vc" / key
    return root / "plain_region.bin", root / "ncch_logo.bin"


def cached_auxiliary_regions(family: str) -> NcchAuxiliaryRegions:
    plain_path, logo_path = auxiliary_cache_paths(family)
    plain = plain_path.read_bytes() if plain_path.is_file() else b""
    logo = logo_path.read_bytes() if logo_path.is_file() else b""
    return NcchAuxiliaryRegions(plain=plain, logo=logo)


_INSTALLED = False


def install() -> None:
    """Preserve cached retail NCCH auxiliary regions during VC packaging."""
    global _INSTALLED
    if _INSTALLED:
        return

    from . import classic_vc as vc

    previous = getattr(vc, "postprocess_vc_ncch", None)

    def postprocess_vc_ncch(ncch: bytes, family: str) -> bytes:
        result = previous(ncch, family) if callable(previous) else ncch
        key = family.strip().lower()
        if key not in _SUPPORTED:
            return result
        auxiliary = cached_auxiliary_regions(key)
        if not auxiliary.plain and not auxiliary.logo:
            return result
        return apply_ncch_auxiliary_regions(
            result,
            plain=auxiliary.plain,
            logo=auxiliary.logo,
        )

    vc.postprocess_vc_ncch = postprocess_vc_ncch
    _INSTALLED = True
