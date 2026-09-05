from __future__ import annotations

import hashlib

import pytest

from romm_vita_manager.classic_vc_ncch_regions import (
    apply_ncch_auxiliary_regions,
    extract_ncch_auxiliary_regions,
)


def _generated_ncch() -> tuple[bytes, bytes, bytes]:
    """Build the minimal layout emitted by agbcia's generated VC NCCH writer."""
    header = bytearray(0x200)
    header[0x100:0x104] = b"NCCH"
    exheader = bytes((index * 5) & 0xFF for index in range(0x800))
    exefs = (b"EXEFS" * 0x100)[:0x400]
    romfs = (b"ROMFS" * 0x200)[:0x600]

    exefs_offset = 5
    exefs_size = len(exefs) // 0x200
    romfs_offset = exefs_offset + exefs_size
    romfs_size = len(romfs) // 0x200
    total_units = 1 + len(exheader) // 0x200 + exefs_size + romfs_size

    header[0x104:0x108] = total_units.to_bytes(4, "little")
    header[0x180:0x184] = (0x400).to_bytes(4, "little")
    header[0x1A0:0x1A4] = exefs_offset.to_bytes(4, "little")
    header[0x1A4:0x1A8] = exefs_size.to_bytes(4, "little")
    header[0x1B0:0x1B4] = romfs_offset.to_bytes(4, "little")
    header[0x1B4:0x1B8] = romfs_size.to_bytes(4, "little")
    return bytes(header) + exheader + exefs + romfs, exefs, romfs


def test_auxiliary_regions_restore_retail_logo_plain_layout_without_changing_payloads() -> None:
    generated, exefs, romfs = _generated_ncch()
    logo = bytes((index * 7) & 0xFF for index in range(0x2000))
    plain = b"[SDK+NINTENDO:SYNTHETIC]".ljust(0x200, b"\x00")

    result = apply_ncch_auxiliary_regions(generated, logo=logo, plain=plain)

    assert int.from_bytes(result[0x198:0x19C], "little") == 5
    assert int.from_bytes(result[0x19C:0x1A0], "little") == 16
    assert int.from_bytes(result[0x190:0x194], "little") == 21
    assert int.from_bytes(result[0x194:0x198], "little") == 1
    assert int.from_bytes(result[0x1A0:0x1A4], "little") == 22
    assert int.from_bytes(result[0x1B0:0x1B4], "little") == 24
    assert int.from_bytes(result[0x104:0x108], "little") == len(result) // 0x200
    assert result[0x130:0x150] == hashlib.sha256(logo).digest()

    extracted = extract_ncch_auxiliary_regions(result)
    assert extracted.logo == logo
    assert extracted.plain == plain

    exefs_start = int.from_bytes(result[0x1A0:0x1A4], "little") * 0x200
    romfs_start = int.from_bytes(result[0x1B0:0x1B4], "little") * 0x200
    assert result[exefs_start : exefs_start + len(exefs)] == exefs
    assert result[romfs_start : romfs_start + len(romfs)] == romfs


def test_auxiliary_region_postprocessor_is_noop_when_donor_has_neither() -> None:
    generated, _, _ = _generated_ncch()
    assert apply_ncch_auxiliary_regions(generated) == generated


def test_auxiliary_region_postprocessor_supports_plain_region_without_logo() -> None:
    generated, exefs, _ = _generated_ncch()
    plain = b"SDK tags only".ljust(0x200, b"\x00")

    result = apply_ncch_auxiliary_regions(generated, plain=plain)

    assert int.from_bytes(result[0x198:0x19C], "little") == 0
    assert int.from_bytes(result[0x19C:0x1A0], "little") == 0
    assert int.from_bytes(result[0x190:0x194], "little") == 5
    assert int.from_bytes(result[0x194:0x198], "little") == 1
    assert int.from_bytes(result[0x1A0:0x1A4], "little") == 6
    assert result[0x130:0x150] == bytes(0x20)
    exefs_start = int.from_bytes(result[0x1A0:0x1A4], "little") * 0x200
    assert result[exefs_start : exefs_start + len(exefs)] == exefs


def test_auxiliary_region_postprocessor_rejects_wrong_launch_logo_size() -> None:
    generated, _, _ = _generated_ncch()
    with pytest.raises(ValueError, match="0x2000"):
        apply_ncch_auxiliary_regions(generated, logo=b"L" * 0x1000)


def test_auxiliary_region_extractor_rejects_out_of_bounds_donor_region() -> None:
    generated, _, _ = _generated_ncch()
    malformed = bytearray(generated)
    malformed[0x198:0x19C] = (0x4000).to_bytes(4, "little")
    malformed[0x19C:0x1A0] = (16).to_bytes(4, "little")
    with pytest.raises(ValueError, match="outside"):
        extract_ncch_auxiliary_regions(bytes(malformed))
