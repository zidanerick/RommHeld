from pathlib import Path

import pytest

from romm_vita_manager.ds_repair import create_ds_content_directories, plan_ds_repairs
from romm_vita_manager.ds_runtime import DsKnownVersions, detect_ds_profile, inspect_ds_runtime


def _twilight_fixture(root: Path, *, bootstrap_version: str = "2.16.0") -> None:
    (root / "_nds" / "TWiLightMenu").mkdir(parents=True)
    (root / "_nds" / "nds-bootstrap-release.nds").write_bytes(b"nds")
    (root / "_nds" / "nds-bootstrap-release.ver").write_text(
        f"nds-bootstrap v{bootstrap_version}\n", encoding="utf-8"
    )
    (root / "BOOT.NDS").write_bytes(b"boot")
    (root / "roms" / "nds" / "saves").mkdir(parents=True)


def test_shared_twilight_layout_stays_generic_without_hardware_evidence(tmp_path: Path) -> None:
    _twilight_fixture(tmp_path)

    profile = detect_ds_profile(tmp_path)
    report = inspect_ds_runtime(tmp_path)

    assert profile.key == "generic-removable"
    assert report.overall_state == "not_verified"
    assert report.check("twilight-menu").state == "not_verified"
    assert any("shared" in note.lower() for note in report.notes)


def test_explicit_dsi_profile_requires_console_confirmation_for_unlaunch(tmp_path: Path) -> None:
    _twilight_fixture(tmp_path)
    (tmp_path / "hiya.dsi").write_bytes(b"hiya")

    report = inspect_ds_runtime(tmp_path, profile_hint="dsi-homebrew")

    assert report.profile.key == "dsi-homebrew"
    assert report.check("dsi-environment").state == "not_verified"
    assert "console confirmation" in report.check("dsi-environment").label.lower()
    assert report.overall_state == "not_verified"


def test_flashcart_profile_detects_ysmenu_without_claiming_boot_success(tmp_path: Path) -> None:
    _twilight_fixture(tmp_path)
    (tmp_path / "TTMenu").mkdir()
    (tmp_path / "YSMenu.nds").write_bytes(b"ys")

    report = inspect_ds_runtime(tmp_path)

    assert report.profile.key == "ds-flashcart"
    kernel = report.check("flashcart-kernel")
    assert kernel.state == "not_verified"
    assert "YSMenu" in kernel.label
    assert report.overall_state == "not_verified"


def test_boot_alt_is_flashcart_evidence(tmp_path: Path) -> None:
    (tmp_path / "BOOT_ALT.NDS").write_bytes(b"alt")

    assert detect_ds_profile(tmp_path).key == "ds-flashcart"


def test_partial_bootstrap_is_needs_attention(tmp_path: Path) -> None:
    (tmp_path / "_nds").mkdir()
    (tmp_path / "_nds" / "nds-bootstrap-release.nds").write_bytes(b"nds")

    report = inspect_ds_runtime(tmp_path)

    check = report.check("nds-bootstrap")
    assert check.state == "needs_attention"
    assert "Partial" in check.label


def test_bootstrap_outdated_only_against_dated_known_baseline(tmp_path: Path) -> None:
    _twilight_fixture(tmp_path, bootstrap_version="2.13.1")

    report = inspect_ds_runtime(
        tmp_path,
        known_versions=DsKnownVersions(
            nds_bootstrap="2.16.0",
            twilight_menu="27.24.1",
            checked_on="2026-09-06",
        ),
    )

    check = report.check("nds-bootstrap")
    assert check.state == "needs_attention"
    assert check.observed_version == "2.13.1"
    assert check.known_version == "2.16.0"
    assert "2026-09-06" in check.summary


def test_rom_and_save_directories_are_safe_repair_only(tmp_path: Path) -> None:
    (tmp_path / "_nds" / "TWiLightMenu").mkdir(parents=True)

    before = inspect_ds_runtime(tmp_path)
    actions = plan_ds_repairs(before)
    created = create_ds_content_directories(tmp_path)
    after = inspect_ds_runtime(tmp_path)

    assert any(action.key == "create-content-directories" and action.scope == "safe" for action in actions)
    assert {path.relative_to(tmp_path).as_posix() for path in created} == {"roms/nds", "roms/nds/saves"}
    assert after.check("rom-directories").state == "verified"
    assert after.check("save-directories").state == "verified"
    assert not (tmp_path / "BOOT.NDS").exists()


def test_malformed_twilight_config_is_guided_not_automatically_rewritten(tmp_path: Path) -> None:
    _twilight_fixture(tmp_path)
    settings = tmp_path / "_nds" / "TWiLightMenu" / "settings.ini"
    settings.write_text("not-an-ini", encoding="utf-8")

    report = inspect_ds_runtime(tmp_path)
    actions = plan_ds_repairs(report)

    assert report.check("config").state == "needs_attention"
    repair = next(action for action in actions if action.key == "repair-config")
    assert repair.scope == "guided"
    assert settings.read_text(encoding="utf-8") == "not-an-ini"


def test_valid_twilight_config_is_verified(tmp_path: Path) -> None:
    _twilight_fixture(tmp_path)
    settings = tmp_path / "_nds" / "TWiLightMenu" / "settings.ini"
    settings.write_text("[SRLOADER]\nLANGUAGE=0\n", encoding="utf-8")

    assert inspect_ds_runtime(tmp_path).check("config").state == "verified"


def test_3ds_hosted_twilight_is_deferred_and_repairs_refuse_to_write(tmp_path: Path) -> None:
    (tmp_path / "Nintendo 3DS").mkdir()
    (tmp_path / "_nds" / "TWiLightMenu").mkdir(parents=True)

    report = inspect_ds_runtime(tmp_path)

    assert report.profile.key == "3ds-hosted-twilight"
    assert report.profile.owner == "3ds"
    assert plan_ds_repairs(report)[0].key == "defer-3ds"
    with pytest.raises(ValueError, match="3DS-hosted"):
        create_ds_content_directories(tmp_path)
    assert not (tmp_path / "roms").exists()
