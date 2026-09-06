from pathlib import Path

from romm_vita_manager.platform_services import is_web_url
from romm_vita_manager.three_ds_apps import (
    APP_BY_KEY,
    THREE_DS_APPS,
    detect_three_ds_app,
    readiness_component_keys,
    recommended_runtime_keys,
    scan_three_ds_apps,
)
from romm_vita_manager.three_ds_targets import RETROARCH_TARGET_PLATFORM_SLUGS


def test_app_detection_is_case_insensitive(tmp_path: Path):
    marker = tmp_path / "LUMA" / "PAYLOADS"
    marker.mkdir(parents=True)
    (marker / "OPEN_AGB_FIRM.FIRM").write_bytes(b"firm")

    status = detect_three_ds_app(tmp_path, APP_BY_KEY["open-agb-firm"])

    assert status.detected
    assert status.marker == "luma/payloads/open_agb_firm.firm"
    assert status.launch_surface == "luma_payload"
    assert "Luma3DS payload chainloader" in status.detection_note
    assert "SD evidence" in status.detection_note


def test_zero_byte_payload_is_not_called_detected(tmp_path: Path):
    payload = tmp_path / "luma" / "payloads" / "open_agb_firm.firm"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"")

    status = detect_three_ds_app(tmp_path, APP_BY_KEY["open-agb-firm"])

    assert not status.detected
    assert status.marker is None


def test_open_agb_database_without_firm_payload_is_not_called_ready(tmp_path: Path):
    resource = tmp_path / "3ds" / "open_agb_firm"
    resource.mkdir(parents=True)
    (resource / "gba_db.bin").write_bytes(b"database")

    status = detect_three_ds_app(tmp_path, APP_BY_KEY["open-agb-firm"])

    assert not status.detected
    assert status.marker is None


def test_missing_cia_capable_app_preserves_unknown_installed_title_state(tmp_path: Path):
    status = detect_three_ds_app(tmp_path, APP_BY_KEY["fbi"])

    assert not status.detected
    assert "installed CIA title may still be present" in status.detection_note


def test_staged_installer_cias_do_not_satisfy_app_readiness(tmp_path: Path):
    (tmp_path / "FBI.cia").write_bytes(b"installer only")
    (tmp_path / "Universal-Updater.cia").write_bytes(b"installer only")

    fbi = detect_three_ds_app(tmp_path, APP_BY_KEY["fbi"])
    updater = detect_three_ds_app(tmp_path, APP_BY_KEY["universal-updater"])

    assert not fbi.detected
    assert not updater.detected
    assert "installed CIA title may still be present" in fbi.detection_note
    assert "installed CIA title may still be present" in updater.detection_note


def test_known_cia_titles_are_detected_from_mounted_sd_title_tree(tmp_path: Path):
    known_titles = {
        "fbi": "000400000F800100",
        "ftpd": "000400000BEEF500",
        "universal-updater": "0004000004391700",
        "red-viper": "000400000FE7CB00",
        "checkpoint": "000400000BCFFF00",
    }
    title_root = (
        tmp_path
        / "Nintendo 3DS"
        / ("1" * 32)
        / ("2" * 32)
        / "title"
    )
    for title_id in known_titles.values():
        (title_root / title_id[:8] / title_id[8:]).mkdir(parents=True, exist_ok=True)

    statuses = scan_three_ds_apps(tmp_path)

    for app_key, title_id in known_titles.items():
        status = statuses[app_key]
        assert status.detected
        assert status.marker == (
            f"Nintendo 3DS/<ID0>/<ID1>/title/{title_id[:8]}/{title_id[8:]}"
        )
        assert status.title_id == title_id
        assert status.launch_surface == "home_menu"
        assert title_id in status.detection_note
        assert "Installed CIA title" in status.detection_note
        assert "HOME Menu" in status.detection_note


def test_installed_cia_title_is_preferred_over_3dsx_marker(tmp_path: Path):
    fbi_3dsx = tmp_path / "3ds" / "FBI" / "FBI.3dsx"
    fbi_3dsx.parent.mkdir(parents=True)
    fbi_3dsx.write_bytes(b"3dsx")
    title_id = "000400000F800100"
    (
        tmp_path
        / "Nintendo 3DS"
        / ("1" * 32)
        / ("2" * 32)
        / "title"
        / title_id[:8]
        / title_id[8:]
    ).mkdir(parents=True)

    status = detect_three_ds_app(tmp_path, APP_BY_KEY["fbi"])

    assert status.detected
    assert status.title_id == title_id
    assert status.launch_surface == "home_menu"


def test_3dsx_marker_reports_homebrew_launcher_surface(tmp_path: Path):
    fbi_3dsx = tmp_path / "3ds" / "FBI" / "FBI.3dsx"
    fbi_3dsx.parent.mkdir(parents=True)
    fbi_3dsx.write_bytes(b"3dsx")

    status = detect_three_ds_app(tmp_path, APP_BY_KEY["fbi"])

    assert status.detected
    assert status.title_id is None
    assert status.launch_surface == "homebrew_launcher"
    assert "Homebrew Launcher" in status.detection_note


def test_unrelated_sd_title_does_not_false_positive_cia_capable_apps(tmp_path: Path):
    title_root = (
        tmp_path
        / "Nintendo 3DS"
        / ("A" * 32)
        / ("B" * 32)
        / "title"
        / "00040000"
        / "01234500"
    )
    title_root.mkdir(parents=True)

    statuses = scan_three_ds_apps(tmp_path)

    for app_key in ("fbi", "ftpd", "universal-updater", "red-viper", "checkpoint"):
        assert not statuses[app_key].detected


def test_scan_detects_foundation_transfer_and_twilight_assets_without_launcher_claim(tmp_path: Path):
    (tmp_path / "boot.firm").write_bytes(b"firm")
    (tmp_path / "boot.3dsx").write_bytes(b"3dsx")
    ftpd = tmp_path / "3ds" / "ftpd"
    ftpd.mkdir(parents=True)
    (ftpd / "ftpd.3dsx").write_bytes(b"ftp")
    (tmp_path / "_nds" / "TWiLightMenu").mkdir(parents=True)
    (tmp_path / "_nds" / "nds-bootstrap").mkdir()

    statuses = scan_three_ds_apps(tmp_path)

    assert statuses["luma"].detected
    assert statuses["homebrew-launcher"].detected
    assert statuses["ftpd"].detected
    assert not statuses["twilight"].detected
    assert statuses["twilight"].marker == "_nds/TWiLightMenu; _nds/nds-bootstrap"
    assert statuses["twilight"].launch_surface == "assets_only"
    assert "do not prove" in statuses["twilight"].detection_note
    assert not statuses["red-viper"].detected


def test_twilight_assets_require_launcher_confirmation(tmp_path: Path):
    (tmp_path / "_nds" / "TWiLightMenu").mkdir(parents=True)
    partial = detect_three_ds_app(tmp_path, APP_BY_KEY["twilight"])
    assert not partial.detected
    assert partial.marker is None

    (tmp_path / "_nds" / "nds-bootstrap").mkdir()
    complete = detect_three_ds_app(tmp_path, APP_BY_KEY["twilight"])
    assert not complete.detected
    assert complete.marker == "_nds/TWiLightMenu; _nds/nds-bootstrap"
    assert complete.launch_surface == "assets_only"
    assert "launchable frontend or HOME Menu title" in complete.detection_note


def test_retroarch_data_folders_do_not_prove_launchable_frontend(tmp_path: Path):
    (tmp_path / "RetroArch" / "Cores").mkdir(parents=True)

    status = detect_three_ds_app(tmp_path, APP_BY_KEY["retroarch"])

    assert not status.detected
    assert status.marker is not None
    assert status.launch_surface == "assets_only"
    assert "do not prove" in status.detection_note


def test_content_directories_do_not_false_positive_as_runtime_installations(tmp_path: Path):
    (tmp_path / "roms" / "virtualboy").mkdir(parents=True)
    (tmp_path / "3ds" / "DaedalusX64" / "Roms").mkdir(parents=True)
    (tmp_path / "BOOT.NDS").write_bytes(b"unrelated nds homebrew")

    assert not detect_three_ds_app(tmp_path, APP_BY_KEY["red-viper"]).detected
    assert not detect_three_ds_app(tmp_path, APP_BY_KEY["daedalusx64"]).detected
    assert not detect_three_ds_app(tmp_path, APP_BY_KEY["twilight"]).detected
    assert not detect_three_ds_app(tmp_path, APP_BY_KEY["homebrew-launcher"]).detected


def test_retroarch_app_metadata_matches_audited_3ds_target_set():
    assert set(APP_BY_KEY["retroarch"].platform_slugs) == set(
        RETROARCH_TARGET_PLATFORM_SLUGS
    )
    assert "virtualboy" in APP_BY_KEY["retroarch"].platform_slugs
    assert "n64" not in APP_BY_KEY["retroarch"].platform_slugs
    assert "amiga" not in APP_BY_KEY["retroarch"].platform_slugs
    assert "scummvm" not in APP_BY_KEY["retroarch"].platform_slugs
    assert not APP_BY_KEY["retroarch"].marker_confirms_launchable


def test_all_readiness_apps_have_valid_web_upstream_urls():
    assert THREE_DS_APPS
    assert all(is_web_url(app.upstream_url) for app in THREE_DS_APPS)


def test_runtime_recommendations_are_platform_specific():
    assert recommended_runtime_keys(["gba"]) == ("open-agb-firm", "retroarch")
    assert recommended_runtime_keys(["nds"]) == ("twilight",)
    assert recommended_runtime_keys(["virtualboy"]) == ("red-viper",)
    assert recommended_runtime_keys(["n64"]) == ("daedalusx64",)
    assert recommended_runtime_keys(["nds", "n64", "nds"]) == (
        "twilight",
        "daedalusx64",
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
