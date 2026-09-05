from __future__ import annotations

import pytest

import romm_vita_manager.classic_vc as classic_vc
import romm_vita_manager.classic_vc_donor_validation as donor_validation


def _gb_rom(*, cgb_flag: int) -> bytes:
    data = bytearray(0x200)
    data[0x143] = cgb_flag
    return bytes(data)


def _valid_target_rom(*, cgb_flag: int) -> bytes:
    data = bytearray(0x8000)
    data[0x134:0x13C] = b"ROMMHELD"
    data[0x143] = cgb_flag
    data[0x147] = 0x00
    data[0x148] = 0x00
    data[0x149] = 0x00
    checksum = 0
    for value in data[0x134:0x14D]:
        checksum = (checksum - value - 1) & 0xFF
    data[0x14D] = checksum
    return bytes(data)


def _payload(monkeypatch: pytest.MonkeyPatch, data: bytes, path: str = "/rom/TEST.rom") -> None:
    monkeypatch.setattr(
        donor_validation,
        "_classic_donor_rom_payload",
        lambda donor_cia, boot9, vc: (path, data),
    )


def test_nes_donor_requires_tnes_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    _payload(monkeypatch, _gb_rom(cgb_flag=0))
    with pytest.raises(ValueError, match="TNES runtime"):
        donor_validation.validate_classic_donor_family("donor", "boot9", "nes", object())


def test_nes_donor_accepts_tnes_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    _payload(monkeypatch, b"TNES" + bytes(12) + b"payload")
    donor_validation.validate_classic_donor_family("donor", "boot9", "nes", object())


def test_gbc_donor_requires_colour_cartridge_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    _payload(monkeypatch, _gb_rom(cgb_flag=0x00))
    with pytest.raises(ValueError, match="monochrome Game Boy ROM"):
        donor_validation.validate_classic_donor_family("donor", "boot9", "gbc", object())

    _payload(monkeypatch, _gb_rom(cgb_flag=0x80))
    donor_validation.validate_classic_donor_family("donor", "boot9", "gbc", object())


def test_gb_donor_rejects_colour_cartridge(monkeypatch: pytest.MonkeyPatch) -> None:
    _payload(monkeypatch, _gb_rom(cgb_flag=0xC0))
    with pytest.raises(ValueError, match="Game Boy Color ROM"):
        donor_validation.validate_classic_donor_family("donor", "boot9", "gb", object())

    _payload(monkeypatch, _gb_rom(cgb_flag=0x00))
    donor_validation.validate_classic_donor_family("donor", "boot9", "gb", object())


def test_gb_target_accepts_valid_monochrome_header():
    rom = _valid_target_rom(cgb_flag=0x00)
    assert donor_validation.validate_gameboy_target_rom(rom, "gb") == rom


def test_gbc_target_accepts_valid_colour_header():
    rom = _valid_target_rom(cgb_flag=0x80)
    assert donor_validation.validate_gameboy_target_rom(rom, "gbc") == rom


def test_gb_target_rejects_colour_cartridge():
    with pytest.raises(ValueError, match="Game Boy Color target"):
        donor_validation.validate_gameboy_target_rom(_valid_target_rom(cgb_flag=0xC0), "gb")


def test_gbc_target_rejects_monochrome_cartridge():
    with pytest.raises(ValueError, match="Game Boy target"):
        donor_validation.validate_gameboy_target_rom(_valid_target_rom(cgb_flag=0x00), "gbc")


def test_gameboy_target_rejects_bad_header_checksum():
    rom = bytearray(_valid_target_rom(cgb_flag=0x00))
    rom[0x134] ^= 0x01
    with pytest.raises(ValueError, match="header checksum"):
        donor_validation.validate_gameboy_target_rom(bytes(rom), "gb")


def test_live_classic_prepare_path_applies_target_validation():
    rom = _valid_target_rom(cgb_flag=0x80)
    assert classic_vc.prepare_classic_rom(rom, "gbc") == rom
    with pytest.raises(ValueError, match="Game Boy Color target"):
        classic_vc.prepare_classic_rom(rom, "gb")
