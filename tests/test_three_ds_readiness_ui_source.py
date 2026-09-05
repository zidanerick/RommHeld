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
