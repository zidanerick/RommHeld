from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest

from romm_vita_manager import classic_vc
from romm_vita_manager.classic_vc_hardware_fix import (
    validate_classic_package_identity,
    validate_retail_romfs,
)
from romm_vita_manager.classic_vc_title_fix import hardware_safe_classic_title_id


ROOT = Path(__file__).resolve().parents[1]


def _align(value: int, boundary: int) -> int:
    return (value + boundary - 1) // boundary * boundary


def _hash_blocks(data: bytes, block_size: int) -> bytes:
    return b"".join(
        hashlib.sha256(data[offset : offset + block_size].ljust(block_size, b"\x00")).digest()
        for offset in range(0, len(data), block_size)
    )


def test_package_init_exposes_hardware_safe_classic_title_ids() -> None:
    for family in ("gb", "gbc"):
        expected = hardware_safe_classic_title_id(1234, family)
        actual = classic_vc.classic_title_id_for_romm_id(1234, family)
        assert actual == expected
        assert actual[:4] == bytes.fromhex("00040000")
        unique_id = int.from_bytes(actual[4:7], "big")
        variation = actual[7]
        assert 0x0E0000 <= unique_id <= 0x0EFFFF
        assert variation == 0


def test_active_classic_builder_accepts_deployment_title_id_override() -> None:
    signature = inspect.signature(classic_vc.build_classic_vc_cia)
    override = signature.parameters.get("title_id_override")

    assert override is not None
    assert override.default is None

    deploy_source = (ROOT / "romm_vita_manager" / "classic_vc_deploy.py").read_text(
        encoding="utf-8"
    )
    assert "self.config, title_id = persist_registered_title_id(self.family, self.game.rom_id)" in deploy_source
    assert "title_id_override=title_id" in deploy_source


def test_retail_romfs_layout_is_independently_verifiable() -> None:
    files = {
        "/config.ini": b"mode=cgb\n",
        "/rom/TEST.000": bytes(range(251)) * 29,
        "/lang/EU-English.lang": b"english",
        "/shaders/test.shbin": b"shader" * 37,
    }
    romfs = classic_vc.build_romfs(files)
    validate_retail_romfs(romfs)

    assert romfs[:4] == b"IVFC"
    assert int.from_bytes(romfs[4:8], "little") == 0x10000
    assert int.from_bytes(romfs[0x54:0x58], "little") == 0x5C
    assert int.from_bytes(romfs[0x58:0x5C], "little") == 0

    block = 0x1000
    master_size = int.from_bytes(romfs[0x08:0x0C], "little")
    level1_size = int.from_bytes(romfs[0x14:0x1C], "little")
    level2_size = int.from_bytes(romfs[0x2C:0x34], "little")
    level3_size = int.from_bytes(romfs[0x44:0x4C], "little")

    level3_physical = 0x1000
    level1_physical = level3_physical + _align(level3_size, block)
    level2_physical = level1_physical + _align(level1_size, block)

    level3 = romfs[level3_physical : level3_physical + level3_size]
    level1 = romfs[level1_physical : level1_physical + level1_size]
    level2 = romfs[level2_physical : level2_physical + level2_size]
    master = romfs[0x60 : 0x60 + master_size]

    assert _hash_blocks(level3, block) == level2
    assert _hash_blocks(level2, block) == level1
    assert _hash_blocks(level1, block) == master

    # File data starts on a 16-byte boundary and every individual file offset
    # stored in the metadata is also 16-byte aligned.
    file_meta_offset = int.from_bytes(level3[0x1C:0x20], "little")
    file_meta_size = int.from_bytes(level3[0x20:0x24], "little")
    file_data_offset = int.from_bytes(level3[0x24:0x28], "little")
    assert file_data_offset % 0x10 == 0
    cursor = 0
    while cursor < file_meta_size:
        base = file_meta_offset + cursor
        assert int.from_bytes(level3[base + 0x08 : base + 0x10], "little") % 0x10 == 0
        name_size = int.from_bytes(level3[base + 0x1C : base + 0x20], "little")
        cursor += 0x20 + _align(name_size, 4)
    assert cursor == file_meta_size


def test_retail_romfs_preflight_rejects_corruption() -> None:
    romfs = bytearray(classic_vc.build_romfs({"/rom/TEST.000": b"ROM" * 1500}))
    romfs[0x1000 + 0x40] ^= 0x80
    with pytest.raises(ValueError, match="hash tree"):
        validate_retail_romfs(bytes(romfs))


def test_package_identity_preflight_checks_every_title_layer() -> None:
    from agbcia.formats import ncch as ncch_format
    from agbcia.formats import ticket as ticket_format
    from agbcia.formats import tmd as tmd_format

    title_id = hardware_safe_classic_title_id(77, "gbc")
    disk_id = title_id[::-1]
    donor_exheader = bytearray(0x800)
    donor_exheader[0x400:] = bytes((index * 13) & 0xFF for index in range(0x400))
    exheader = bytearray(donor_exheader)
    exheader[0x1C8:0x1D0] = disk_id
    exheader[0x200:0x208] = disk_id
    exheader = bytes(exheader)

    ncch = ncch_format.build(
        ncch_format.Ncch(
            title_id=title_id,
            product_code="CTR-N-RHC77",
            exheader=exheader,
        )
    )
    ticket = ticket_format.build(ticket_format.Ticket(title_id=title_id))
    content = tmd_format.content_chunk_from_data(content_id=0, content_index=0, data=ncch)
    tmd = tmd_format.build(tmd_format.Tmd(title_id=title_id, contents=(content,)))

    validate_classic_package_identity(
        ncch=ncch,
        exheader=exheader,
        donor_exheader=bytes(donor_exheader),
        title_id=title_id,
        ticket=ticket,
        tmd=tmd,
    )

    bad_ticket = bytearray(ticket)
    bad_ticket[0x1DC] ^= 1
    with pytest.raises(ValueError, match="ticket title ID"):
        validate_classic_package_identity(
            ncch=ncch,
            exheader=exheader,
            donor_exheader=bytes(donor_exheader),
            title_id=title_id,
            ticket=bytes(bad_ticket),
            tmd=tmd,
        )
