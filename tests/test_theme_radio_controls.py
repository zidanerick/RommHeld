from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dark_theme_radio_indicators_remain_visible() -> None:
    source = (ROOT / "romm_vita_manager/theme.py").read_text(encoding="utf-8")

    assert "QRadioButton::indicator {" in source
    assert "width: 14px;" in source
    assert "height: 14px;" in source
    assert "border: 1px solid #8E8E93;" in source
    assert "QRadioButton::indicator:hover" in source
    assert "QRadioButton::indicator:checked" in source
    assert "qradialgradient(" in source
