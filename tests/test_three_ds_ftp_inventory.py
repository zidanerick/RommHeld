from __future__ import annotations

from romm_vita_manager.three_ds_ftp import ThreeDSFtpSettings
from romm_vita_manager.three_ds_ftp_inventory import (
    merge_three_ds_app_inventories,
    scan_three_ds_apps_ftp,
)
from romm_vita_manager.three_ds_apps import APP_BY_KEY, ThreeDSAppStatus


class FakeInventoryBackend:
    tree: dict[str, list[dict[str, str | int]]] = {}

    def __init__(self, settings: ThreeDSFtpSettings):
        self.settings = settings
        self.connected = False

    def connect(self):
        self.connected = True
        return "/"

    def close(self):
        self.connected = False

    def list_directory(self, path: str = ""):
        key = path.strip("/")
        return list(self.tree.get(key, []))


def _dir(name: str) -> dict[str, str | int]:
    return {"name": name, "type": "dir", "size": 0}


def _file(name: str, size: int = 1) -> dict[str, str | int]:
    return {"name": name, "type": "file", "size": size}


def test_ftp_inventory_detects_homebrew_files_case_insensitively():
    FakeInventoryBackend.tree = {
        "": [_dir("3DS")],
        "3DS": [_dir("Universal-Updater"), _dir("DaedalusX64")],
        "3DS/Universal-Updater": [_file("UNIVERSAL-UPDATER.3DSX")],
        "3DS/DaedalusX64": [_file("DAEDALUSX64.3DSX")],
    }
    statuses = scan_three_ds_apps_ftp(
        ThreeDSFtpSettings("192.0.2.3"),
        backend_factory=FakeInventoryBackend,
    )

    assert statuses["universal-updater"].detected
    assert statuses["universal-updater"].source == "ftp"
    assert statuses["universal-updater"].launch_surface == "homebrew_launcher"
    assert "Live FTP evidence" in statuses["universal-updater"].detection_note
    assert "Homebrew Launcher" in statuses["universal-updater"].detection_note
    assert statuses["daedalusx64"].detected
    assert statuses["ftpd"].detected
    assert statuses["ftpd"].source == "ftp_live"
    assert "live ftpd connection" in statuses["ftpd"].detection_note.lower()


def test_ftp_inventory_rejects_zero_byte_payload_marker():
    FakeInventoryBackend.tree = {
        "": [_dir("luma")],
        "luma": [_dir("payloads")],
        "luma/payloads": [_file("open_agb_firm.firm", size=0)],
    }

    statuses = scan_three_ds_apps_ftp(
        ThreeDSFtpSettings("192.0.2.3"),
        backend_factory=FakeInventoryBackend,
    )

    assert not statuses["open-agb-firm"].detected
    assert statuses["open-agb-firm"].marker is None


def test_ftp_inventory_detects_known_cia_title_tree():
    id0 = "1" * 32
    id1 = "2" * 32
    title_id = "000400000BCFFF00"
    FakeInventoryBackend.tree = {
        "": [_dir("Nintendo 3DS")],
        "Nintendo 3DS": [_dir(id0)],
        f"Nintendo 3DS/{id0}": [_dir(id1)],
        f"Nintendo 3DS/{id0}/{id1}": [_dir("title")],
        f"Nintendo 3DS/{id0}/{id1}/title": [_dir(title_id[:8])],
        f"Nintendo 3DS/{id0}/{id1}/title/{title_id[:8]}": [_dir(title_id[8:])],
        f"Nintendo 3DS/{id0}/{id1}/title/{title_id[:8]}/{title_id[8:]}": [],
    }
    statuses = scan_three_ds_apps_ftp(
        ThreeDSFtpSettings("192.0.2.3"),
        backend_factory=FakeInventoryBackend,
    )

    checkpoint = statuses["checkpoint"]
    assert checkpoint.detected
    assert checkpoint.title_id == title_id
    assert checkpoint.source == "ftp"
    assert checkpoint.launch_surface == "home_menu"
    assert "live FTP SD title tree" in checkpoint.detection_note
    assert "HOME Menu" in checkpoint.detection_note


def test_ftp_cia_title_evidence_is_preferred_over_3dsx_marker():
    id0 = "A" * 32
    id1 = "B" * 32
    title_id = "000400000BCFFF00"
    FakeInventoryBackend.tree = {
        "": [_dir("3ds"), _dir("Nintendo 3DS")],
        "3ds": [_dir("Checkpoint")],
        "3ds/Checkpoint": [_file("Checkpoint.3dsx")],
        "Nintendo 3DS": [_dir(id0)],
        f"Nintendo 3DS/{id0}": [_dir(id1)],
        f"Nintendo 3DS/{id0}/{id1}": [_dir("title")],
        f"Nintendo 3DS/{id0}/{id1}/title": [_dir(title_id[:8])],
        f"Nintendo 3DS/{id0}/{id1}/title/{title_id[:8]}": [_dir(title_id[8:])],
        f"Nintendo 3DS/{id0}/{id1}/title/{title_id[:8]}/{title_id[8:]}": [],
    }

    status = scan_three_ds_apps_ftp(
        ThreeDSFtpSettings("192.0.2.3"),
        backend_factory=FakeInventoryBackend,
    )["checkpoint"]

    assert status.title_id == title_id
    assert status.launch_surface == "home_menu"


def test_twilight_remote_assets_require_launcher_confirmation():
    FakeInventoryBackend.tree = {
        "": [_dir("_nds")],
        "_nds": [_dir("TWiLightMenu")],
        "_nds/TWiLightMenu": [],
    }
    partial = scan_three_ds_apps_ftp(
        ThreeDSFtpSettings("192.0.2.3"),
        backend_factory=FakeInventoryBackend,
    )
    assert not partial["twilight"].detected
    assert partial["twilight"].marker is None

    FakeInventoryBackend.tree["_nds"].append(_dir("nds-bootstrap"))
    FakeInventoryBackend.tree["_nds/nds-bootstrap"] = []
    complete = scan_three_ds_apps_ftp(
        ThreeDSFtpSettings("192.0.2.3"),
        backend_factory=FakeInventoryBackend,
    )
    assert not complete["twilight"].detected
    assert complete["twilight"].marker == "_nds/TWiLightMenu; _nds/nds-bootstrap"
    assert complete["twilight"].launch_surface == "assets_only"
    assert "do not prove" in complete["twilight"].detection_note


def test_merge_prefers_positive_ftp_evidence_over_negative_mounted_scan():
    local = {
        "checkpoint": ThreeDSAppStatus(APP_BY_KEY["checkpoint"], False),
    }
    remote = {
        "checkpoint": ThreeDSAppStatus(
            APP_BY_KEY["checkpoint"],
            True,
            "3ds/Checkpoint/Checkpoint.3dsx",
            source="ftp",
        ),
    }

    merged = merge_three_ds_app_inventories(local, remote)

    assert merged["checkpoint"].detected
    assert merged["checkpoint"].source == "ftp"


def test_merge_prefers_installed_title_over_3dsx_positive_evidence():
    local = {
        "checkpoint": ThreeDSAppStatus(
            APP_BY_KEY["checkpoint"],
            True,
            "3ds/Checkpoint/Checkpoint.3dsx",
            source="mounted_sd",
        ),
    }
    remote = {
        "checkpoint": ThreeDSAppStatus(
            APP_BY_KEY["checkpoint"],
            True,
            "Nintendo 3DS/<ID0>/<ID1>/title/00040000/0BCFFF00",
            title_id="000400000BCFFF00",
            source="ftp",
        ),
    }

    merged = merge_three_ds_app_inventories(local, remote)

    assert merged["checkpoint"].title_id == "000400000BCFFF00"
    assert merged["checkpoint"].launch_surface == "home_menu"


def test_merge_keeps_unconfirmed_remote_runtime_file_evidence():
    local = {
        "twilight": ThreeDSAppStatus(APP_BY_KEY["twilight"], False),
    }
    remote = {
        "twilight": ThreeDSAppStatus(
            APP_BY_KEY["twilight"],
            False,
            "_nds/TWiLightMenu; _nds/nds-bootstrap",
            source="ftp",
        ),
    }

    merged = merge_three_ds_app_inventories(local, remote)

    assert not merged["twilight"].detected
    assert merged["twilight"].source == "ftp"
    assert merged["twilight"].marker is not None
