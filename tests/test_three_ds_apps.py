from pathlib import Path

from romm_vita_manager.three_ds_apps import (
    APP_BY_KEY,
    detect_three_ds_app,
    readiness_component_keys,
    recommended_runtime_keys,
    scan_three_ds_apps,
)


def test_app_detection_is_case_insensitive(tmp_path: Path):
    marker = tmp_path / "LUMA" / "PAYLOADS"
    marker.mkdir(parents=True)
    (marker / "OPEN_AGB_FIRM.FIRM").write_bytes(b"firm")

    status = detect_three_ds_app(tmp_path, APP_BY_KEY["open-agb-firm"])

    assert status.detected
    assert status.marker == "luma/payloads/open_agb_firm.firm"
    assert "SD evidence" in status.detection_note


def test_missing_cia_capable_app_preserves_unknown_installed_title_state(tmp_path: Path):
    status = detect_three_ds_app(tmp_path, APP_BY_KEY["fbi"])

    assert not status.detected
    assert "installed CIA title may still be present" in status.detection_note


def test_scan_detects_foundation_transfer_and_runtime_markers(tmp_path: Path):
    (tmp_path / "boot.firm").write_bytes(b"firm")
    (tmp_path / "boot.3dsx").write_bytes(b"3dsx")
    ftpd = tmp_path / "3ds" / "ftpd"
    ftpd.mkdir(parents=True)
    (ftpd / "ftpd.3dsx").write_bytes(b"ftp")
    twilight = tmp_path / "_nds" / "TWiLightMenu"
    twilight.mkdir(parents=True)

    statuses = scan_three_ds_apps(tmp_path)

    assert statuses["luma"].detected
    assert statuses["homebrew-launcher"].detected
    assert statuses["ftpd"].detected
    assert statuses["twilight"].detected
    assert not statuses["red-viper"].detected


def test_content_directories_do_not_false_positive_as_runtime_installations(tmp_path: Path):
    (tmp_path / "roms" / "virtualboy").mkdir(parents=True)
    (tmp_path / "BOOT.NDS").write_bytes(b"unrelated nds homebrew")

    assert not detect_three_ds_app(tmp_path, APP_BY_KEY["red-viper"]).detected
    assert not detect_three_ds_app(tmp_path, APP_BY_KEY["twilight"]).detected


def test_runtime_recommendations_are_platform_specific():
    assert recommended_runtime_keys(["gba"]) == ("open-agb-firm", "retroarch")
    assert recommended_runtime_keys(["nds"]) == ("twilight",)
    assert recommended_runtime_keys(["virtualboy"]) == ("red-viper",)
    assert recommended_runtime_keys(["n64"]) == ("daedalusx64", "retroarch")
    assert recommended_runtime_keys(["nds", "n64", "nds"]) == (
        "twilight",
        "daedalusx64",
        "retroarch",
    )


def test_readiness_components_include_only_requested_transport_and_install_dependencies():
    basic = readiness_component_keys(["gba"], needs_ftp=False, needs_cia_install=False)
    assert basic == (
        "luma",
        "homebrew-launcher",
        "universal-updater",
        "open-agb-firm",
        "retroarch",
    )

    full = readiness_component_keys(["nds"], needs_ftp=True, needs_cia_install=True)
    assert full == (
        "luma",
        "homebrew-launcher",
        "universal-updater",
        "ftpd",
        "fbi",
        "twilight",
    )


def test_dsp_firmware_is_console_generated_not_downloadable():
    dsp = APP_BY_KEY["dsp-firmware"]
    assert dsp.install_policy == "console_generated"
