from __future__ import annotations

import pytest

from romm_vita_manager import classic_vc
from romm_vita_manager.classic_vc_title_fix import hardware_safe_classic_title_id
from romm_vita_manager.nes_vc import ines_to_tnes


def _ines(
    *,
    mapper: int,
    prg_16k: int = 8,
    chr_8k: int = 0,
    vertical: bool = True,
    battery: bool = False,
    trainer: bool = False,
    prg_ram_units: int = 0,
) -> bytes:
    flags6 = ((mapper & 0x0F) << 4)
    flags6 |= 0x01 if vertical else 0
    flags6 |= 0x02 if battery else 0
    flags6 |= 0x04 if trainer else 0
    flags7 = mapper & 0xF0
    header = bytearray(16)
    header[:4] = b"NES\x1A"
    header[4] = prg_16k
    header[5] = chr_8k
    header[6] = flags6
    header[7] = flags7
    header[8] = prg_ram_units
    training = b"T" * 512 if trainer else b""
    prg = bytes((index * 7) & 0xFF for index in range(prg_16k * 16384))
    chr_ = bytes((index * 11) & 0xFF for index in range(chr_8k * 8192))
    return bytes(header) + training + prg + chr_


def test_uxrom_conversion_matches_retail_renegade_tnes_header_shape() -> None:
    # The supplied Renegade donor is TNES mapper 6, 16x8KiB PRG, no CHR,
    # no WRAM, vertical mirroring, no battery. Use synthetic payload bytes but
    # require the exact header structure observed in that retail donor.
    source = _ines(mapper=2, prg_16k=8, chr_8k=0, vertical=True)
    result = ines_to_tnes(source)

    assert result[:16] == b"TNES" + bytes((6, 16, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0))
    assert len(result) == 16 + 128 * 1024
    assert result[16:] == source[16:]


def test_tnes_conversion_removes_ines_trainer_before_prg() -> None:
    source = _ines(mapper=0, prg_16k=2, chr_8k=1, trainer=True)
    result = ines_to_tnes(source)

    assert result[:4] == b"TNES"
    assert len(result) == 16 + 2 * 16384 + 8192
    assert result[16:32] == source[16 + 512 : 16 + 512 + 16]


@pytest.mark.parametrize(
    ("ines_mapper", "tnes_mapper"),
    [(0, 0), (1, 1), (9, 2), (4, 3), (10, 4), (5, 5), (2, 6), (3, 7), (7, 8)],
)
def test_all_documented_tnes_mapper_families_are_mapped(ines_mapper: int, tnes_mapper: int) -> None:
    result = ines_to_tnes(_ines(mapper=ines_mapper, prg_16k=2, chr_8k=1))
    assert result[4] == tnes_mapper


def test_unsupported_mapper_is_rejected_instead_of_building_bad_cia() -> None:
    with pytest.raises(ValueError, match="Use RetroArch"):
        ines_to_tnes(_ines(mapper=66, prg_16k=2, chr_8k=1))


def test_truncated_ines_payload_is_rejected() -> None:
    source = _ines(mapper=0, prg_16k=2, chr_8k=1)
    with pytest.raises(ValueError, match="shorter than"):
        ines_to_tnes(source[:-500])


def test_nes_family_is_installed_into_validated_classic_backend() -> None:
    assert "nes" in classic_vc._CLASSIC_FAMILIES
    assert classic_vc._CLASSIC_ROM_EXTENSIONS["nes"] == (".nes",)
    title_id = hardware_safe_classic_title_id(1234, "nes")
    assert title_id[:4] == bytes.fromhex("00040000")
    unique_id = int.from_bytes(title_id[4:7], "big")
    assert 0x0E0000 <= unique_id <= 0x0EFFFF
    assert title_id[7] == 0
