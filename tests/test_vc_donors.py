from pathlib import Path

import pytest

import romm_vita_manager.vc_donors as vc_donors


def _fake_cia(path: Path, *, title_id: str = "000400000007e500") -> None:
    data = bytearray(0x5000)
    data[0:4] = (0x2020).to_bytes(4, "little")
    data[0x08:0x0C] = (0xA00).to_bytes(4, "little")
    data[0x0C:0x10] = (0x350).to_bytes(4, "little")
    data[0x10:0x14] = (0xB64).to_bytes(4, "little")
    ticket_offset = 0x2040 + 0xA00
    data[ticket_offset + 0x1DC : ticket_offset + 0x1E4] = bytes.fromhex(title_id)
    tmd_offset = (ticket_offset + 0x350 + 63) & ~63
    data[tmd_offset : tmd_offset + 4] = (0x00010004).to_bytes(4, "big")
    tmd_header = tmd_offset + 4 + 0x13C
    data[tmd_header + 0x9E : tmd_header + 0xA0] = (2).to_bytes(2, "big")
    path.write_bytes(data)


def _stub_boot9_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vc_donors, "validate_boot9", lambda path: "full")


def test_donor_family_mapping_covers_implemented_nintendo_3ds_vc_platforms():
    assert vc_donors.donor_family_for_platform("gb").key == "gb"
    assert vc_donors.donor_family_for_platform("gbc").key == "gbc"
    assert vc_donors.donor_family_for_platform("gba").key == "gba"
    assert vc_donors.donor_family_for_platform("nes").key == "nes"
    assert vc_donors.donor_family_for_platform("snes").key == "snes"
    assert vc_donors.donor_family_for_platform("gamegear").key == "gamegear"
    # The native NES builder currently accepts cartridge iNES/NES2 payloads;
    # Famicom/FDS remain explicit RetroArch routes until those source formats
    # are independently implemented.
    assert vc_donors.donor_family_for_platform("famicom") is None
    assert vc_donors.donor_family_for_platform("fds") is None
    assert vc_donors.donor_family_for_platform("genesis") is None


def test_snes_donor_is_new_3ds_only():
    assert vc_donors.donor_family("snes").requires_new_3ds


def test_implemented_family_injectors_are_explicit():
    assert vc_donors.donor_family("gba").injector_key == "agbcia"
    for key in ("gb", "gbc", "nes", "gamegear", "snes"):
        assert vc_donors.donor_family(key).injector_key == "classic_vc"


def test_configure_and_read_donor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(vc_donors, "save_config", lambda config: None)
    cia = tmp_path / "donor.cia"
    _fake_cia(cia)

    config = vc_donors.configure_donor({}, "gb", cia)
    assert vc_donors.configured_donor_path(config, "gb") == cia
    info = vc_donors.configured_donor_info(config, "gb")
    assert info["title_id"] == "000400000007e500"
    assert info["content_count"] == 2


def test_invalid_cia_is_rejected(tmp_path: Path):
    cia = tmp_path / "bad.cia"
    cia.write_bytes(b"not a cia")
    with pytest.raises(ValueError):
        vc_donors.inspect_cia_container(cia)


def test_gba_donor_rejects_non_agb_firm_title_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(vc_donors, "save_config", lambda config: None)
    cia = tmp_path / "not-gba.cia"
    _fake_cia(cia, title_id="0004000000075400")
    with pytest.raises(ValueError, match="AGB_FIRM"):
        vc_donors.configure_donor({}, "gba", cia)


def test_invalid_boot9_is_rejected(tmp_path: Path):
    boot9 = tmp_path / "boot9.bin"
    boot9.write_bytes(bytes(0x10000))
    with pytest.raises(ValueError, match="known retail"):
        vc_donors.validate_boot9(boot9)


def test_gb_readiness_accepts_configured_donor_and_boot9(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(vc_donors, "save_config", lambda config: None)
    _stub_boot9_validation(monkeypatch)
    donor = tmp_path / "donor.cia"
    boot9 = tmp_path / "boot9.bin"
    _fake_cia(donor)
    boot9.write_bytes(b"boot9")

    config = vc_donors.configure_donor({}, "gb", donor)
    config = vc_donors.configure_boot9(config, boot9)
    ready, message = vc_donors.donor_readiness(config, "gb")
    assert ready
    assert "configured" in message


def test_cached_gbc_runtime_is_ready_without_source_paths(monkeypatch: pytest.MonkeyPatch):
    import romm_vita_manager.classic_vc_assets as assets

    sentinel = object()
    monkeypatch.setattr(assets, "configured_classic_runtime", lambda config, family: sentinel)
    ready, message = vc_donors.donor_readiness({"classic_vc": {"gbc": {}}}, "gbc")
    assert ready
    assert "cached" in message


def test_stale_classic_cache_is_not_reported_ready(monkeypatch: pytest.MonkeyPatch):
    import romm_vita_manager.classic_vc_assets as assets

    monkeypatch.setattr(assets, "configured_classic_runtime", lambda config, family: None)
    ready, message = vc_donors.donor_readiness(
        {"classic_vc": {"gbc": {"cache_version": 4}}},
        "gbc",
    )
    assert not ready
    assert "Configure a Game Boy Color Virtual Console donor CIA" in message


def test_gba_readiness_requires_donor_and_boot9(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(vc_donors, "save_config", lambda config: None)
    _stub_boot9_validation(monkeypatch)
    donor = tmp_path / "gba.cia"
    boot9 = tmp_path / "boot9.bin"
    _fake_cia(donor, title_id="0004000000f12300")
    boot9.write_bytes(b"boot9")

    config = vc_donors.configure_donor({}, "gba", donor)
    ready, message = vc_donors.donor_readiness(config, "gba")
    assert not ready
    assert "boot9" in message

    config = vc_donors.configure_boot9(config, boot9)
    ready, _ = vc_donors.donor_readiness(config, "gba")
    assert ready


def test_snes_readiness_requires_new_3ds_and_defers_seed_lookup_to_preparation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(vc_donors, "save_config", lambda config: None)
    _stub_boot9_validation(monkeypatch)
    donor = tmp_path / "snes.cia"
    boot9 = tmp_path / "boot9.bin"
    _fake_cia(donor, title_id="000400000f706600")
    boot9.write_bytes(b"boot9")
    config = vc_donors.configure_donor({}, "snes", donor)
    config = vc_donors.configure_boot9(config, boot9)
    ready, message = vc_donors.donor_readiness(config, "snes")
    assert ready
    assert "public seed" in message
    assert "New Nintendo 3DS" in message
