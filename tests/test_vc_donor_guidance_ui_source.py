from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_classic_vc_runtime_card_surfaces_profile_aware_donor_guidance() -> None:
    source = _source("romm_vita_manager/classic_vc_deploy.py")

    assert "runtime_guidance_summary(self.config, self.family)" in source
    assert "guidance_for_family(self.family)" in source
    assert "self._refresh_runtime_guidance()" in source
    assert 'self.runtime_guidance.setToolTip("\\n".join(guidance.details))' in source


def test_gba_vc_runtime_card_surfaces_profile_aware_donor_guidance() -> None:
    source = _source("romm_vita_manager/gba_vc_deploy.py")

    assert 'runtime_guidance_summary(self.config, "gba")' in source
    assert 'guidance_for_family("gba")' in source
    assert "self._refresh_donor_guidance()" in source
    assert 'self.donor_guidance.setToolTip("\\n".join(guidance.details))' in source
