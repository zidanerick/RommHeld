from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_three_ds_library_applies_saved_runtime_preference_before_deploy() -> None:
    source = (ROOT / "romm_vita_manager" / "three_ds_library.py").read_text(
        encoding="utf-8"
    )

    assert "from .preferences import get_device_preference" in source
    assert "preferred_target_key" in source
    assert 'preference = get_device_preference(self.config, "3ds")' in source
    assert "preferred = preferred_target_key(game.platform_slug, preference)" in source
    assert "preferred_index = self.target_combo.findData(preferred)" in source
    assert "self.target_combo.setCurrentIndex(preferred_index)" in source
    assert "self.open_manager_callback(game, target_key)" in source
