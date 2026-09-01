from pathlib import Path

from romm_vita_manager.app import _vita_target


def test_vita_target_stays_under_ux0(tmp_path):
    (tmp_path / "ux0").mkdir()
    target = _vita_target(tmp_path, "ux0:/data/test.bin")
    assert target == (tmp_path / "ux0" / "data" / "test.bin").resolve()
