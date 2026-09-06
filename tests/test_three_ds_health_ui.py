from PySide6.QtWidgets import QApplication

from romm_vita_manager.three_ds_apps import APP_BY_KEY, ThreeDSAppStatus
from romm_vita_manager.three_ds_readiness_ui import ThreeDSReadinessDialog


def _app():
    return QApplication.instance() or QApplication([])


def _dialog():
    _app()
    return ThreeDSReadinessDialog(None, needs_ftp=False)


def _select(dialog: ThreeDSReadinessDialog, app_key: str) -> None:
    for row in range(dialog.component_list.count()):
        item = dialog.component_list.item(row)
        if item.data(item.data.__self__.UserRole) if False else False:
            pass
        if str(item.data(256) or "") == app_key:
            dialog.component_list.setCurrentRow(row)
            dialog._selection_changed(item, None)
            return
    raise AssertionError(f"App row not found: {app_key}")


def _select_by_key(dialog: ThreeDSReadinessDialog, app_key: str) -> None:
    from PySide6.QtCore import Qt

    for row in range(dialog.component_list.count()):
        item = dialog.component_list.item(row)
        if str(item.data(Qt.ItemDataRole.UserRole) or "") == app_key:
            dialog.component_list.setCurrentRow(row)
            dialog._selection_changed(item, None)
            return
    raise AssertionError(f"App row not found: {app_key}")


def test_installed_cia_presence_is_not_presented_as_launch_verified():
    dialog = _dialog()
    dialog._statuses["fbi"] = ThreeDSAppStatus(
        APP_BY_KEY["fbi"],
        True,
        title_id="000400000F800100",
        source="mounted_sd",
    )
    dialog._render_inventory("fbi")
    _select_by_key(dialog, "fbi")

    text = dialog.detail_text.text()
    assert "Health: Present · Launch not verified" in text
    assert "filesystem evidence cannot prove" in text
    assert "Remote Install" in text
    dialog.close()


def test_live_ftpd_connection_is_presented_as_operationally_verified():
    dialog = _dialog()
    dialog._statuses["ftpd"] = ThreeDSAppStatus(
        APP_BY_KEY["ftpd"],
        True,
        marker="live ftpd connection",
        source="ftp_live",
    )
    dialog._render_inventory("ftpd")
    _select_by_key(dialog, "ftpd")

    text = dialog.detail_text.text()
    assert "Health: Working · Live connection verified" in text
    assert "connected to the running ftpd service" in text
    dialog.close()


def test_ftpd_scan_failure_shows_repair_sequence_instead_of_only_detected_state():
    dialog = _dialog()
    dialog._statuses["ftpd"] = ThreeDSAppStatus(
        APP_BY_KEY["ftpd"],
        True,
        title_id="000400000BEEF500",
        source="mounted_sd",
    )
    dialog._last_ftp_scan_error = "The 3DS refused the FTP connection."
    dialog._render_inventory("ftpd")
    _select_by_key(dialog, "ftpd")

    text = dialog.detail_text.text()
    assert "Health: Needs attention · Service unreachable" in text
    assert "Launch ftpd on the 3DS" in text
    assert "IP address and port" in text
    assert "Universal-Updater" in text
    dialog.close()


def test_inventory_copy_explicitly_separates_presence_from_health():
    source = __import__(
        "pathlib"
    ).Path("romm_vita_manager/three_ds_readiness_ui.py").read_text(encoding="utf-8")

    assert "Presence does not prove an application launches correctly" in source
    assert "assess_three_ds_app_health" in source
    assert "Health: {health.label}" in source
