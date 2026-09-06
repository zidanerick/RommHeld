from romm_vita_manager.three_ds_app_health import assess_three_ds_app_health
from romm_vita_manager.three_ds_apps import APP_BY_KEY, ThreeDSAppStatus


def _status(key: str, detected: bool, *, marker=None, title_id=None, source="mounted_sd"):
    return ThreeDSAppStatus(
        APP_BY_KEY[key],
        detected,
        marker=marker,
        title_id=title_id,
        source=source,
    )


def test_live_ftpd_is_the_only_direct_operational_verification():
    health = assess_three_ds_app_health(
        _status("ftpd", True, marker="live ftpd connection", source="ftp_live")
    )

    assert health.state == "verified"
    assert "Live connection verified" in health.label
    assert "connected to the running ftpd service" in health.summary


def test_installed_ftpd_without_live_connection_is_not_called_working():
    health = assess_three_ds_app_health(
        _status(
            "ftpd",
            True,
            title_id="000400000BEEF500",
            marker="Nintendo 3DS/<ID0>/<ID1>/title/00040000/0BEEF500",
        )
    )

    assert health.state == "not_verified"
    assert "Launch not verified" in health.label
    assert "Launch ftpd" in health.troubleshooting_text


def test_ftpd_connection_failure_surfaces_repair_steps_even_when_installed():
    health = assess_three_ds_app_health(
        _status("ftpd", True, title_id="000400000BEEF500"),
        ftp_error="The 3DS refused the FTP connection.",
    )

    assert health.state == "needs_attention"
    assert "Service unreachable" in health.label
    assert "refused" in health.summary
    assert "IP address and port" in health.troubleshooting_text
    assert "Universal-Updater" in health.troubleshooting_text


def test_installed_fbi_is_presence_not_remote_install_health():
    health = assess_three_ds_app_health(
        _status("fbi", True, title_id="000400000F800100")
    )

    assert health.state == "not_verified"
    assert "Remote Install" in health.summary
    assert "small lawful CIA" in health.troubleshooting_text


def test_red_viper_health_guidance_includes_dsp_troubleshooting():
    health = assess_three_ds_app_health(
        _status("red-viper", True, title_id="000400000FE7CB00")
    )

    assert health.state == "not_verified"
    assert "DSP firmware" in health.troubleshooting_text


def test_twilight_assets_without_launch_surface_are_needs_attention():
    health = assess_three_ds_app_health(
        _status(
            "twilight",
            False,
            marker="_nds/TWiLightMenu; _nds/nds-bootstrap",
        )
    )

    assert health.state == "needs_attention"
    assert "Runtime assets only" in health.label
    assert "repair the full maintained" in health.troubleshooting_text


def test_retroarch_assets_without_frontend_are_needs_attention():
    health = assess_three_ds_app_health(
        _status("retroarch", False, marker="RetroArch; RetroArch/Cores")
    )

    assert health.state == "needs_attention"
    assert "launchable frontend is not confirmed" in health.summary
    assert "platform-specific core" in health.troubleshooting_text


def test_missing_app_keeps_console_confirmation_and_install_repair_boundary():
    health = assess_three_ds_app_health(_status("checkpoint", False))

    assert health.state == "missing"
    assert "no reliable evidence" in health.summary
    assert "checked sources" in health.summary
    assert "preparation/updater/upstream" in health.troubleshooting_text
