from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readiness_ui_surfaces_runtime_evidence_without_new_navigation() -> None:
    source = (ROOT / "romm_vita_manager" / "three_ds_readiness_ui.py").read_text(
        encoding="utf-8"
    )

    assert "scan_twilight_runtime" in source
    assert "scan_retroarch_route" in source
    assert 'if app_key == "twilight":' in source
    assert 'if app_key != "retroarch":' in source
    assert "CIA files are installer evidence, not proof that the core title is installed." in source
    assert "Cores-Notused" in source
    assert "Current 3DS SNES cores are not recommended for achievements" in source
    assert "current official 3DS core bundle does not provide an audited N64 core" in source
    assert "ThreeDSReadinessDialog" in source


def test_3ds_external_link_buttons_use_shared_qt_service_with_failure_feedback() -> None:
    readiness = (
        ROOT / "romm_vita_manager" / "three_ds_readiness_ui.py"
    ).read_text(encoding="utf-8")
    setup = (ROOT / "romm_vita_manager" / "three_ds_setup.py").read_text(
        encoding="utf-8"
    )

    for source in (readiness, setup):
        assert "open_external_url" in source
        assert "is_web_url" in source
        assert "webbrowser" not in source
        assert '"Unable to open browser"' in source
        assert "Copy the URL above and open it manually." in source

    assert 'QPushButton("Open upstream")' in readiness
    assert 'QPushButton("Open ftpd release")' in setup
    assert 'QPushButton("Open FBI release")' in setup
    assert 'QPushButton("Open selected release")' in setup


def test_readiness_ui_keeps_direct_staging_and_updater_assistance_distinct() -> None:
    source = (ROOT / "romm_vita_manager" / "three_ds_readiness_ui.py").read_text(
        encoding="utf-8"
    )

    assert "UNIVERSAL_UPDATER_ASSIST_POLICIES" in source
    assert '"manual_bundle_or_updater"' in source
    assert '"prefer_universal_updater"' in source
    assert "def _uses_universal_updater_assist" in source
    assert 'package_for_app(app_key) is None' in source
    assert 'self.stage_button.setText(f"Prepare {package.name}")' in source
    assert 'self.stage_button.setText("Prepare Universal-Updater")' in source
    assert 'self.stage_button.setText("Show updater steps")' in source
    assert "launch Universal-Updater and search for" in source
    assert "Homebrew Launcher build and does not claim that a CIA title is installed" in source
    assert 'self.stage_button.setText("Generate on console")' in source
    assert 'self.stage_button.setText("No automatic install")' in source
