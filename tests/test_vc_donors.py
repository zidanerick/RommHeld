from pathlib import Path

import pytest

import romm_vita_manager.vc_donors as vc_donors


def test_donor_family_mapping_covers_nintendo_3ds_vc_platforms():
    assert vc_donors.donor_family_for_platform("gb").key == "gb"
    assert vc_donors.donor_family_for_platform("gbc").key == "gbc"
    assert vc_donors.donor_family_for_platform("gba").key == "gba"
    assert vc_donors.donor_family_for_platform("nes").key == "nes"
    assert vc_donors.donor_family_for_platform("famicom").key == "nes"
    assert vc_donors.donor_family_for_platform("fds").key == "nes"
    assert vc_donors.donor_family_for_platform("snes").key == "snes"
    assert vc_donors.donor_family_for_platform("gamegear").key == "gamegear"
    assert vc_donors.donor_family_for_platform("genesis") is None


def test_snes_donor_is_new_3ds_only():
    assert vc_donors.donor_family("snes").requires_new_3ds


def test_gba_is_only_implemented_family_injector():
    assert vc_donors.donor_family("gba").injector_key == "agbcia"
    for key in ("gb", "gbc", "nes", "snes", "gamegear"):
        assert vc_donors.donor_family(key).injector_key is None


def test_configure_and_read_donor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(vc_donors, "save_config", lambda config: None)
    cia = tmp_path / "donor.cia"
    cia.write_bytes(b"cia")

    config = vc_donors.configure_donor({}, "gb", cia)
    assert vc_donors.configured_donor_path(config, "gb") == cia


def test_readiness_refuses_unimplemented_injector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(vc_donors, "save_config", lambda config: None)
    donor = tmp_path / "donor.cia"
    boot9 = tmp_path / "boot9.bin"
    donor.write_bytes(b"cia")
    boot9.write_bytes(b"boot9")

    config = vc_donors.configure_donor({}, "gb", donor)
    config = vc_donors.configure_boot9(config, boot9)
    ready, message = vc_donors.donor_readiness(config, "gb")
    assert not ready
    assert "not implemented" in message


def test_gba_readiness_requires_donor_and_boot9(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(vc_donors, "save_config", lambda config: None)
    donor = tmp_path / "gba.cia"
    boot9 = tmp_path / "boot9.bin"
    donor.write_bytes(b"cia")
    boot9.write_bytes(b"boot9")

    config = vc_donors.configure_donor({}, "gba", donor)
    ready, message = vc_donors.donor_readiness(config, "gba")
    assert not ready
    assert "boot9" in message

    config = vc_donors.configure_boot9(config, boot9)
    ready, _ = vc_donors.donor_readiness(config, "gba")
    assert ready
