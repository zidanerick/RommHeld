from pathlib import Path

from romm_vita_manager.three_ds_readiness import (
    build_readiness_requirements,
    evaluate_readiness,
)


def _importance(requirements):
    return {item.app_key: item.importance for item in requirements}


def test_ftp_readiness_requires_luma_homebrew_and_ftpd_but_only_recommends_updater():
    requirements = build_readiness_requirements(
        needs_ftp=True,
        needs_cia_install=False,
        include_utilities=False,
    )
    importance = _importance(requirements)

    assert importance["luma"] == "required"
    assert importance["homebrew-launcher"] == "required"
    assert importance["ftpd"] == "required"
    assert importance["universal-updater"] == "recommended"
    assert "fbi" not in importance


def test_cia_workflow_requires_fbi_and_recommends_checkpoint():
    requirements = build_readiness_requirements(
        needs_ftp=False,
        needs_cia_install=True,
        include_utilities=False,
    )
    importance = _importance(requirements)

    assert importance["fbi"] == "required"
    assert importance["checkpoint"] == "recommended"
    assert "ftpd" not in importance


def test_selected_runtime_becomes_required_without_requiring_alternatives():
    requirements = build_readiness_requirements(
        ["open_agb_firm"],
        needs_ftp=False,
        include_utilities=False,
    )
    importance = _importance(requirements)

    assert importance["open-agb-firm"] == "required"
    assert "retroarch" not in importance


def test_red_viper_recommends_console_generated_dsp_firmware():
    requirements = build_readiness_requirements(
        ["red_viper"],
        needs_ftp=False,
        include_utilities=False,
    )
    importance = _importance(requirements)

    assert importance["red-viper"] == "required"
    assert importance["dsp-firmware"] == "recommended"


def test_report_distinguishes_definite_missing_from_installed_title_confirmation(tmp_path: Path):
    report = evaluate_readiness(
        tmp_path,
        ["red_viper"],
        needs_ftp=False,
        include_utilities=False,
    )

    missing = {item.requirement.app_key for item in report.missing_required}
    unconfirmed = {item.requirement.app_key for item in report.unconfirmed_required}
    assert "luma" in missing
    assert "red-viper" in unconfirmed
    assert report.state == "missing_required"


def test_report_is_ready_when_required_sd_evidence_is_present(tmp_path: Path):
    (tmp_path / "boot.firm").write_bytes(b"firm")
    payloads = tmp_path / "luma" / "payloads"
    payloads.mkdir(parents=True)
    (payloads / "open_agb_firm.firm").write_bytes(b"firm")

    report = evaluate_readiness(
        tmp_path,
        ["open_agb_firm"],
        needs_ftp=False,
        include_utilities=False,
    )

    assert report.missing_required == ()
    assert report.unconfirmed_required == ()
    assert report.state == "ready"
