from __future__ import annotations

from pathlib import Path

import pytest

from romm_vita_manager.app import _vita_target


def test_vita_target_maps_ux0_path(tmp_path):
    (tmp_path / "ux0").mkdir()
    assert _vita_target(tmp_path, "ux0:/data/example.bin") == (tmp_path / "ux0" / "data/example.bin").resolve()


def test_vita_target_rejects_escape(tmp_path):
    (tmp_path / "ux0").mkdir()
    with pytest.raises(ValueError):
        _vita_target(tmp_path, "ux0:/../outside.bin")
