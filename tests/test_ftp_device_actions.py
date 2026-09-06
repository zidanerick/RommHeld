from pathlib import Path

from romm_vita_manager.three_ds_ftp import ThreeDSFtpSettings
from romm_vita_manager.vita_ftp import VitaFtpSettings
from romm_vita_manager.workspace_dashboard import WorkspaceDashboardWindow


def test_device_page_exposes_contextual_ftp_files_for_vita_and_3ds_only():
    source = Path("romm_vita_manager/workspace_dashboard.py").read_text(encoding="utf-8")

    assert 'QPushButton("FTP files")' in source
    assert "workspace_vita_ftp_files_action" in source
    assert "workspace_3ds_ftp_files_action" in source
    assert "open_vita_ftp_files" in source
    assert "open_3ds_ftp_files" in source
    assert "workspace_ds_ftp_files_action" not in source
    assert "def open_ds_ftp_files" not in source


def test_contextual_ftp_actions_follow_endpoint_presence():
    source = Path("romm_vita_manager/workspace_dashboard.py").read_text(encoding="utf-8")

    assert "self.workspace_vita_ftp_files_action.setEnabled(bool(ftp_host))" in source
    assert "self.workspace_3ds_ftp_files_action.setEnabled(bool(host))" in source
    assert "Configure the VitaShell FTP endpoint in Send file / configure FTP first." in source
    assert "Configure the ftpd endpoint in Connection setup first." in source


def test_workspace_builds_console_specific_file_manager_settings():
    three_ds = WorkspaceDashboardWindow._three_ds_ftp_settings(
        {
            "host": "192.0.2.3",
            "port": "5001",
            "username": "user",
            "password": "secret",
            "remote_root": "/sd",
        }
    )
    assert three_ds == ThreeDSFtpSettings(
        host="192.0.2.3",
        port=5001,
        username="user",
        password="secret",
        remote_root="/sd",
    )
    assert WorkspaceDashboardWindow._three_ds_ftp_settings({}) is None

    vita = WorkspaceDashboardWindow._vita_ftp_settings(
        {
            "host": "192.0.2.4",
            "port": "1338",
            "username": "anonymous",
            "remote_root": "/ux0:/data",
        }
    )
    assert vita == VitaFtpSettings(
        host="192.0.2.4",
        port=1338,
        username="anonymous",
        password="",
        remote_root="/ux0:/data",
    )
    assert WorkspaceDashboardWindow._vita_ftp_settings({}) is None
