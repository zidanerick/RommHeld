from __future__ import annotations

import pytest

from romm_vita_manager import classic_vc
from romm_vita_manager.classic_vc_title_fix import hardware_safe_classic_title_id
from romm_vita_manager.snes_vc import (
    build_snes_data_bin,
    inspect_snes_rom,
    parse_snes_data_bin,
)


def _snes_rom(*, mapping: str = "lorom", cartridge_type: int = 0x00, copier_header: bool = False) -> bytes:
    size = 0x10000
    rom = bytearray(size)
    offset = 0x7FC0 if mapping == "lorom" else 0xFFC0
    title = b"ROMMHELD SYNTHETIC VC"
    rom[offset : offset + 21] = title[:21].ljust(21, b" ")
    rom[offset + 0x15] = 0x20 if mapping == "lorom" else 0x21
    rom[offset + 0x16] = cartridge_type
    rom[offset + 0x17] = 0x09
    rom[offset + 0x18] = 0x05 if cartridge_type in {1, 2} else 0
    checksum = 0x1234
    rom[offset + 0x1C : offset + 0x1E] = (checksum ^ 0xFFFF).to_bytes(2, "little")
    rom[offset + 0x1E : offset + 0x20] = checksum.to_bytes(2, "little")
    rom[offset + 0x3C : offset + 0x3E] = (0x8000).to_bytes(2, "little")
    payload = bytes(rom)
    return bytes(512) + payload if copier_header else payload


def test_standard_lorom_builds_documented_data_bin() -> None:
    source = _snes_rom(mapping="lorom", cartridge_type=0x02)
    info = inspect_snes_rom(source)
    assert info.mapping == "lorom"
    assert info.vc_rom_type == 0x14
    assert info.checksum_valid

    data = build_snes_data_bin(source, product_id="KTR-RH01")
    parsed = parse_snes_data_bin(data)
    assert parsed.product_id == "KTR-RH01"
    assert parsed.preset_id == 0
    assert parsed.rom_type == 0x14
    assert parsed.rom_start == 0x60
    assert data[parsed.rom_start : parsed.rom_end] == source


def test_standard_hirom_uses_nintendo_hirom_type() -> None:
    source = _snes_rom(mapping="hirom")
    data = build_snes_data_bin(source, product_id="KTR-RH02")
    parsed = parse_snes_data_bin(data)
    assert parsed.rom_type == 0x15
    assert data[0x41] == 0x15


def test_512_byte_smc_copier_header_is_removed() -> None:
    source = _snes_rom(mapping="lorom", copier_header=True)
    data = build_snes_data_bin(source, product_id="KTR-RH03")
    parsed = parse_snes_data_bin(data)
    assert parsed.rom_end - parsed.rom_start == len(source) - 512
    assert data[parsed.rom_start : parsed.rom_end] == source[512:]


def test_enhancement_chip_rom_is_rejected_to_retroarch() -> None:
    with pytest.raises(ValueError, match="Use RetroArch"):
        inspect_snes_rom(_snes_rom(cartridge_type=0x03))


def test_malformed_data_bin_is_rejected() -> None:
    data = bytearray(build_snes_data_bin(_snes_rom(), product_id="KTR-RH04"))
    data[4:8] = (123).to_bytes(4, "little")
    with pytest.raises(ValueError, match="inconsistent"):
        parse_snes_data_bin(bytes(data))


def test_snes_family_is_installed_in_validated_classic_backend() -> None:
    assert "snes" in classic_vc._CLASSIC_FAMILIES
    assert classic_vc._CLASSIC_ROM_EXTENSIONS["snes"] == (".sfc", ".smc")
    title_id = hardware_safe_classic_title_id(333, "snes")
    assert title_id[:4] == bytes.fromhex("00040000")
    assert title_id[7] == 0


def test_snes_auxiliary_romfs_metadata_tracks_generated_product_id_and_icon() -> None:
    data_bin = build_snes_data_bin(_snes_rom(), product_id="KTR-RH00")
    files = {
        "/data.bin": data_bin,
        "/KTR-OLD1.icn": b"old-donor-icon",
        "/shader/default.shbin": b"shader",
    }
    icon = b"generated-smdh"
    result = classic_vc.prepare_runtime_aux_files(
        files,
        "snes",
        "KTR-N-RABC",
        icon,
    )

    assert "/KTR-OLD1.icn" not in result
    assert result["/KTR-RABC.icn"] == icon
    assert parse_snes_data_bin(result["/data.bin"]).product_id == "KTR-RABC"
    assert result["/shader/default.shbin"] == b"shader"


def test_snes_icon_is_marked_new3ds_only() -> None:
    from agbcia.formats import smdh

    small = bytes(smdh.ICON_SMALL_DIMENSIONS[0] * smdh.ICON_SMALL_DIMENSIONS[1] * 3)
    large = bytes(smdh.ICON_LARGE_DIMENSIONS[0] * smdh.ICON_LARGE_DIMENSIONS[1] * 3)
    source = smdh.build(smdh.Smdh(titles={}, icon_small=small, icon_large=large))

    result = classic_vc.postprocess_vc_icon(source, "snes")
    parsed = smdh.parse(result)
    assert parsed.flags & smdh.FLAG_NEW_3DS


def test_snes_ncch_is_marked_for_snake_new3ds_platform() -> None:
    ncch = bytearray(0x200)
    ncch[0x100:0x104] = b"NCCH"
    ncch[0x18C] = 1

    result = classic_vc.postprocess_vc_ncch(bytes(ncch), "snes")
    assert result[0x18C] == 2

    ordinary = classic_vc.postprocess_vc_ncch(bytes(ncch), "gbc")
    assert ordinary[0x18C] == 1
