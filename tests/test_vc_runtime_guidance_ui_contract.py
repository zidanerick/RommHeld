from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLASSIC_DEPLOY = ROOT / "romm_vita_manager" / "classic_vc_deploy.py"
GBA_DEPLOY = ROOT / "romm_vita_manager" / "gba_vc_deploy.py"


def test_classic_vc_runtime_tooltip_uses_configured_profile_details():
    source = CLASSIC_DEPLOY.read_text(encoding="utf-8")

    assert "runtime_guidance_details" in source
    assert 'runtime_guidance_details(self.config, self.family)' in source
    assert 'guidance.details' not in source


def test_gba_runtime_tooltip_uses_configured_profile_details():
    source = GBA_DEPLOY.read_text(encoding="utf-8")

    assert "runtime_guidance_details" in source
    assert 'runtime_guidance_details(self.config, "gba")' in source
    assert 'guidance.details' not in source
    assert "two reusable assets" not in source
