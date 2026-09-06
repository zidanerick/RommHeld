from __future__ import annotations

from pathlib import Path

import pytest

from romm_vita_manager.three_ds_app_health import assess_three_ds_app_health
from romm_vita_manager.three_ds_apps import APP_BY_KEY, ThreeDSAppStatus, detect_three_ds_app
from romm_vita_manager.three_ds_ftp import ThreeDSFtpSettings
from romm_vita_manager.three_ds_ftp_inventory import scan_three_ds_apps_ftp
from romm_vita_manager.three_ds_packages import package_for_app, validate_staging_root
from romm_vita_manager.three_ds_runtime_details import (
    scan_retroarch_route,
    scan_twilight_runtime,
)


class _FakeInventoryBackend:
    tree: dict[str, list[dict[str, str | int]]] = {}

    def __init__(self, settings: ThreeDSFtpSettings):
        self.settings = settings

    def connect(self):
        return "/"

    def close(self):
        return None

    def list_directory(self, path: str = ""):
        return list(self.tree.get(path.strip("/"), []))


def _dir(name: str) -> dict[str, str | int]:
    return {"name": name, "type": "dir", "size": 0}


def _file(name: str, size: int = 1) -> dict[str, str | int]:
    return {"name": name, "type": "file", "size": size}


def _write_open_agb_payload(root: Path) -> None:
    payload = root / "luma" / "payloads" / "open_agb_firm.firm"
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_bytes(b"firm")


def _write_open_agb_support(root: Path) -> None:
    support = root / "3ds" / "open_agb_firm" / "gba_db.bin"
    support.parent.mkdir(parents=True, exist_ok=True)
    support.write_bytes(b"database")


def _install_sd_title(root: Path, title_id: str) -> None:
    (
        root
        / "Nintendo 3DS"
        / ("1" * 32)
        / ("2" * 32)
        / "title"
        / title_id[:8]
        / title_id[8:]
    ).mkdir(parents=True, exist_ok=True)


def test_existing_positive_evidence_remains_present_without_claiming_launch_health(tmp_path: Path):
    fbi = tmp_path / "3ds" / "FBI" / "FBI.3dsx"
    fbi.parent.mkdir(parents=True)
    fbi.write_bytes(b"3dsx")

    status = detect_three_ds_app(tmp_path, APP_BY_KEY["fbi"])

    assert status.detected
    assert status.state == "present"
    assert status.state_label == "Present · Launch not verified"
    assert status.launch_surface == "homebrew_launcher"


def test_live_ftpd_is_healthy_operational_evidence():
    status = ThreeDSAppStatus(
        APP_BY_KEY["ftpd"],
        True,
        marker="live ftpd connection",
        source="ftp_live",
    )

    assert status.state == "healthy"
    assert status.state_label == "Healthy"
    assert "Live connection verified" in assess_three_ds_app_health(status).label


def test_open_agb_payload_only_is_partial_not_complete(tmp_path: Path):
    _write_open_agb_payload(tmp_path)

    status = detect_three_ds_app(tmp_path, APP_BY_KEY["open-agb-firm"])
    health = assess_three_ds_app_health(status)

    assert status.detected  # The Luma launch-surface payload is genuinely present.
    assert status.state == "partial"
    assert status.missing_health_markers == ("3ds/open_agb_firm/gba_db.bin",)
    assert "installation is incomplete" in status.detection_note
    assert health.state == "needs_attention"
    assert health.label == "Partial installation · Support files missing"
    assert "copy both open_agb_firm.firm" in health.troubleshooting_text
    assert package_for_app("open-agb-firm") is None


def test_open_agb_release_files_are_present_but_launch_still_unverified(tmp_path: Path):
    _write_open_agb_payload(tmp_path)
    _write_open_agb_support(tmp_path)

    status = detect_three_ds_app(tmp_path, APP_BY_KEY["open-agb-firm"])
    health = assess_three_ds_app_health(status)

    assert status.detected
    assert status.state == "present"
    assert status.missing_health_markers == ()
    assert health.state == "not_verified"
    assert health.label == "Present · Launch not verified"
    assert "payload and required bundled support data are present" in health.summary


def test_open_agb_support_without_payload_is_also_partial(tmp_path: Path):
    _write_open_agb_support(tmp_path)

    status = detect_three_ds_app(tmp_path, APP_BY_KEY["open-agb-firm"])

    assert not status.detected
    assert status.state == "partial"
    assert status.matched_health_markers == ("3ds/open_agb_firm/gba_db.bin",)


def test_twilight_realistic_assets_are_assets_only_until_launcher_is_confirmed(tmp_path: Path):
    (tmp_path / "_nds" / "TWiLightMenu").mkdir(parents=True)
    (tmp_path / "_nds" / "nds-bootstrap").mkdir()
    (tmp_path / "BOOT.NDS").write_bytes(b"nds")

    status = detect_three_ds_app(tmp_path, APP_BY_KEY["twilight"])
    runtime = scan_twilight_runtime(tmp_path)
    health = assess_three_ds_app_health(status)

    assert not status.detected
    assert status.state == "assets_only"
    assert runtime.state == "ready"
    assert runtime.boot_nds
    assert "launcher still requires separate on-console confirmation" in runtime.note
    assert "Runtime assets only" in health.label
    assert "Launcher not verified" in health.label


def test_retroarch_data_tree_without_cores_is_assets_only(tmp_path: Path):
    (tmp_path / "RetroArch" / "assets" / "xmb").mkdir(parents=True)

    status = detect_three_ds_app(tmp_path, APP_BY_KEY["retroarch"])
    route = scan_retroarch_route(tmp_path, "gba")
    health = assess_three_ds_app_health(status)

    assert not status.detected
    assert status.state == "assets_only"
    assert route.state == "confirm_core_on_console"
    assert "No matching core package is visible" in route.note
    assert "Runtime assets only" in health.label
    assert "Launchable core not verified" in health.label


def test_missing_and_unknown_console_states_are_distinct(tmp_path: Path):
    luma = detect_three_ds_app(tmp_path, APP_BY_KEY["luma"])
    checkpoint = detect_three_ds_app(tmp_path, APP_BY_KEY["checkpoint"])

    assert luma.state == "missing"
    assert luma.state_label == "Missing"
    assert checkpoint.state == "unknown"
    assert checkpoint.state_label == "Unknown · Console confirmation required"
    assert assess_three_ds_app_health(checkpoint).label == "Unknown · Console confirmation required"


def test_cia_title_and_3dsx_evidence_keep_distinct_launch_surfaces(tmp_path: Path):
    hbl_root = tmp_path / "hbl"
    fbi = hbl_root / "3ds" / "FBI" / "FBI.3dsx"
    fbi.parent.mkdir(parents=True)
    fbi.write_bytes(b"3dsx")
    hbl_status = detect_three_ds_app(hbl_root, APP_BY_KEY["fbi"])

    cia_root = tmp_path / "cia"
    cia_root.mkdir()
    _install_sd_title(cia_root, "000400000F800100")
    cia_status = detect_three_ds_app(cia_root, APP_BY_KEY["fbi"])

    assert hbl_status.state == "present"
    assert hbl_status.title_id is None
    assert hbl_status.launch_surface == "homebrew_launcher"
    assert cia_status.state == "present"
    assert cia_status.title_id == "000400000F800100"
    assert cia_status.launch_surface == "home_menu"


def test_mounted_sd_and_ftp_open_agb_health_semantics_converge(tmp_path: Path):
    _write_open_agb_payload(tmp_path)
    local = detect_three_ds_app(tmp_path, APP_BY_KEY["open-agb-firm"])

    _FakeInventoryBackend.tree = {
        "": [_dir("luma")],
        "luma": [_dir("payloads")],
        "luma/payloads": [_file("open_agb_firm.firm")],
    }
    remote = scan_three_ds_apps_ftp(
        ThreeDSFtpSettings("192.0.2.3"),
        backend_factory=_FakeInventoryBackend,
    )["open-agb-firm"]

    assert local.state == remote.state == "partial"
    assert local.missing_health_markers == remote.missing_health_markers


def test_mounted_sd_and_ftp_complete_open_agb_semantics_converge(tmp_path: Path):
    _write_open_agb_payload(tmp_path)
    _write_open_agb_support(tmp_path)
    local = detect_three_ds_app(tmp_path, APP_BY_KEY["open-agb-firm"])

    _FakeInventoryBackend.tree = {
        "": [_dir("luma"), _dir("3ds")],
        "luma": [_dir("payloads")],
        "luma/payloads": [_file("open_agb_firm.firm")],
        "3ds": [_dir("open_agb_firm")],
        "3ds/open_agb_firm": [_file("gba_db.bin")],
    }
    remote = scan_three_ds_apps_ftp(
        ThreeDSFtpSettings("192.0.2.3"),
        backend_factory=_FakeInventoryBackend,
    )["open-agb-firm"]

    assert local.state == remote.state == "present"
    assert local.missing_health_markers == remote.missing_health_markers == ()


def test_system_sensitive_and_complex_runtimes_do_not_gain_destructive_direct_repair():
    for app_key in ("luma", "homebrew-launcher", "open-agb-firm", "twilight", "retroarch", "daedalusx64"):
        assert package_for_app(app_key) is None

    assert APP_BY_KEY["luma"].install_policy == "guide_only"
    assert APP_BY_KEY["twilight"].install_policy == "prefer_universal_updater"
    assert APP_BY_KEY["retroarch"].install_policy == "manual_bundle_or_updater"


def test_existing_direct_staging_repair_still_requires_high_confidence_sd(tmp_path: Path):
    assert package_for_app("fbi") is not None
    with pytest.raises(ValueError, match="high-confidence Nintendo 3DS SD-card root"):
        validate_staging_root(tmp_path)
