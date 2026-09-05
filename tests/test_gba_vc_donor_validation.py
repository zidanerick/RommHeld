import hashlib
import struct

import pytest

from romm_vita_manager.gba_vc_donor_validation import inspect_gba_vc_code


def _valid_code(*, rom_size: int = 0x20000) -> bytes:
    rom = bytes((index & 0xFF) for index in range(rom_size))
    config = bytearray(0x324)
    config[4:8] = rom_size.to_bytes(4, "little")
    padding = bytes(0x0C)
    descriptor_offset = rom_size + len(config) + len(padding)
    descriptors = struct.pack("<IIII", 0, 0, rom_size, 0)
    descriptors += struct.pack("<IIII", 1, rom_size, 0x324, 0)
    caa = struct.pack("<4sIII", b".CAA", 1, descriptor_offset, 0x20)
    result = rom + bytes(config) + padding + descriptors + caa
    assert len(result) == rom_size + 0x360
    return result


def test_valid_gba_vc_code_reports_rom_size_and_fingerprint():
    code = _valid_code()
    inspection = inspect_gba_vc_code(code)
    assert inspection.rom_size == 0x20000
    assert inspection.code_sha256 == hashlib.sha256(code).hexdigest()


def test_gba_vc_code_rejects_missing_caa_magic():
    code = bytearray(_valid_code())
    code[-16:-12] = b"FAIL"
    with pytest.raises(ValueError, match="CAA footer"):
        inspect_gba_vc_code(bytes(code))


def test_gba_vc_code_rejects_descriptor_offset_that_does_not_match_footer():
    code = bytearray(_valid_code())
    code[-8:-4] = (0).to_bytes(4, "little")
    with pytest.raises(ValueError, match="descriptor offset"):
        inspect_gba_vc_code(bytes(code))


def test_gba_vc_code_rejects_wrong_descriptor_count():
    code = bytearray(_valid_code())
    code[-4:] = (0x10).to_bytes(4, "little")
    with pytest.raises(ValueError, match="exactly two"):
        inspect_gba_vc_code(bytes(code))


def test_gba_vc_code_rejects_config_rom_size_disagreement():
    code = bytearray(_valid_code())
    rom_size = 0x20000
    code[rom_size + 4 : rom_size + 8] = (rom_size - 4).to_bytes(4, "little")
    with pytest.raises(ValueError, match="ROM-size field disagrees"):
        inspect_gba_vc_code(bytes(code))


def test_gba_vc_code_rejects_non_agb_firm_descriptor_layout():
    code = bytearray(_valid_code())
    descriptor_offset = int.from_bytes(code[-8:-4], "little")
    code[descriptor_offset : descriptor_offset + 4] = (9).to_bytes(4, "little")
    with pytest.raises(ValueError, match="type-0 layout"):
        inspect_gba_vc_code(bytes(code))
