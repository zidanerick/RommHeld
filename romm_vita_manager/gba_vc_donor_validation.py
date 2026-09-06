from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from . import gba_vc


_FOOTER_SIZE = 0x360
_CONFIG_SIZE = 0x324
_CONFIG_PADDING_SIZE = 0x0C
_DESCRIPTOR_SIZE = 0x10
_DESCRIPTOR_COUNT = 2
_CAA_HEADER_SIZE = 0x10
_CAA_MAGIC = b".CAA"
_CAA_VERSION = 1
_CAA_DESCRIPTOR_COUNT_FIELD = _DESCRIPTOR_COUNT << 4
_MAX_GBA_ROM_SIZE = 0x2000000


@dataclass(frozen=True, slots=True)
class GbaVcDonorInspection:
    rom_size: int
    code_sha256: str


def inspect_gba_vc_code(code: bytes) -> GbaVcDonorInspection:
    """Validate the AGB_FIRM ROM/footer layout used by genuine GBA VC titles.

    3dbrew documents ExeFS ``.code`` as the raw GBA ROM followed by a
    0x360-byte footer. The footer ends with two 0x10-byte config descriptors
    and a 0x10-byte ``.CAA`` header. Checking those cross-referenced offsets is
    a substantially stronger donor-family check than relying on a filename,
    product title, or the donor's original retail Title ID.
    """
    data = bytes(code)
    if len(data) <= _FOOTER_SIZE:
        raise ValueError("GBA Virtual Console donor .code is too small to contain a ROM and AGB_FIRM footer.")

    caa_offset = len(data) - _CAA_HEADER_SIZE
    header = data[caa_offset:]
    if header[:4] != _CAA_MAGIC:
        raise ValueError("Selected donor does not contain the GBA Virtual Console .CAA footer.")
    if int.from_bytes(header[4:8], "little") != _CAA_VERSION:
        raise ValueError("GBA Virtual Console donor .CAA footer has an unsupported version.")

    descriptor_offset = int.from_bytes(header[8:12], "little")
    descriptor_count_field = int.from_bytes(header[12:16], "little")
    expected_descriptor_offset = caa_offset - (_DESCRIPTOR_SIZE * _DESCRIPTOR_COUNT)
    if descriptor_count_field != _CAA_DESCRIPTOR_COUNT_FIELD:
        raise ValueError("GBA Virtual Console donor .CAA footer does not describe exactly two config entries.")
    if descriptor_offset != expected_descriptor_offset:
        raise ValueError("GBA Virtual Console donor .CAA descriptor offset is inconsistent with the .code size.")

    table_end = descriptor_offset + (_DESCRIPTOR_SIZE * _DESCRIPTOR_COUNT)
    if descriptor_offset < 0 or table_end != caa_offset:
        raise ValueError("GBA Virtual Console donor descriptor table is outside the .code footer.")

    rom_desc = data[descriptor_offset : descriptor_offset + _DESCRIPTOR_SIZE]
    config_desc = data[descriptor_offset + _DESCRIPTOR_SIZE : table_end]
    rom_type = int.from_bytes(rom_desc[0:4], "little")
    rom_offset = int.from_bytes(rom_desc[4:8], "little")
    rom_size = int.from_bytes(rom_desc[8:12], "little")
    rom_padding = int.from_bytes(rom_desc[12:16], "little")
    config_type = int.from_bytes(config_desc[0:4], "little")
    config_offset = int.from_bytes(config_desc[4:8], "little")
    config_size = int.from_bytes(config_desc[8:12], "little")
    config_padding = int.from_bytes(config_desc[12:16], "little")

    if rom_type != 0 or rom_offset != 0 or rom_padding != 0:
        raise ValueError("GBA Virtual Console donor ROM descriptor is not the AGB_FIRM type-0 layout.")
    if not 0 < rom_size <= _MAX_GBA_ROM_SIZE:
        raise ValueError(f"GBA Virtual Console donor reports an invalid ROM size: {rom_size} bytes.")
    if config_type != 1 or config_offset != rom_size or config_size != _CONFIG_SIZE or config_padding != 0:
        raise ValueError("GBA Virtual Console donor metadata descriptor is not the AGB_FIRM type-1 layout.")

    config_start = rom_size
    expected_descriptor_start = config_start + _CONFIG_SIZE + _CONFIG_PADDING_SIZE
    if descriptor_offset != expected_descriptor_start:
        raise ValueError("GBA Virtual Console donor footer size does not match its ROM/config descriptors.")
    if rom_size + _FOOTER_SIZE != len(data):
        raise ValueError("GBA Virtual Console donor .code is not ROM plus the documented 0x360-byte footer.")

    declared_rom_size = int.from_bytes(data[config_start + 4 : config_start + 8], "little")
    if declared_rom_size != rom_size:
        raise ValueError("GBA Virtual Console donor metadata ROM-size field disagrees with its descriptor.")

    return GbaVcDonorInspection(
        rom_size=rom_size,
        code_sha256=hashlib.sha256(data).hexdigest(),
    )


def inspect_gba_vc_donor(donor_cia: Path, boot9: Path) -> GbaVcDonorInspection:
    donor = gba_vc.read_asset(donor_cia)
    keys = gba_vc.read_asset(boot9)
    ncch = gba_vc._primary_ncch_from_cia(donor)
    code = gba_vc._extract_ncch_exefs_entry(ncch, keys, ".code")
    return inspect_gba_vc_code(code)
