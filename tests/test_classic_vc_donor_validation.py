from __future__ import annotations

import pytest

import romm_vita_manager.classic_vc_donor_validation as donor_validation


def _gb_rom(*, cgb_flag: int) -> bytes:
    data = bytearray(0x200)
    data[0x143] = cgb_flag
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
