from pathlib import Path

import pytest

from romm_vita_manager.open_agb_config import (
    BACKUP_SUFFIX,
    detect_open_agb_config_format,
    parse_open_agb_values,
    update_open_agb_config_text,
    write_open_agb_config,
)


CURRENT_CONFIG = """# user comment
[general]
backlight=64
backlightSteps=5
directBoot=false
useGbaDb=true
useSavesFolder=true
customFutureKey=keep-me

[video]
scaler=matrix
colorProfile=none
contrast=1.0
brightness=0.0
saturation=1.0

[audio]
audioOut=auto
volume=127

[advanced]
saveOverride=false
defaultSave=sram_256k

[input]
RIGHT=RIGHT,CP_RIGHT
"""


def test_current_format_is_recognised_and_values_parse():
    assert detect_open_agb_config_format(CURRENT_CONFIG) == "current"
    values = parse_open_agb_values(CURRENT_CONFIG)
    assert values["general"]["directBoot"] == "false"
    assert values["video"]["scaler"] == "matrix"


def test_legacy_numeric_config_is_rejected():
    legacy = """[general]
backlight=64
[video]
scaler=2
[audio]
audioOut=0
[advanced]
defaultSave=14
"""
    assert detect_open_agb_config_format(legacy) == "legacy"
    with pytest.raises(RuntimeError, match="not recognised as current"):
        update_open_agb_config_text(legacy, {("general", "directBoot"): True})


def test_updates_preserve_comments_unknown_keys_and_unrelated_sections():
    updated = update_open_agb_config_text(
        CURRENT_CONFIG,
        {
            ("general", "directBoot"): True,
            ("video", "scaler"): "none",
            ("video", "colorProfile"): "gba_sp101",
            ("audio", "audioOut"): "headphones",
        },
    )

    assert "# user comment" in updated
    assert "customFutureKey=keep-me" in updated
    assert "RIGHT=RIGHT,CP_RIGHT" in updated
    assert "directBoot=true" in updated
    assert "scaler=none" in updated
    assert "colorProfile=gba_sp101" in updated
    assert "audioOut=headphones" in updated


def test_invalid_values_are_rejected():
    with pytest.raises(ValueError, match="scaler"):
        update_open_agb_config_text(CURRENT_CONFIG, {("video", "scaler"): "magic"})
    with pytest.raises(ValueError, match="backlight"):
        update_open_agb_config_text(CURRENT_CONFIG, {("general", "backlight"): 255})
    with pytest.raises(KeyError, match="Unsupported"):
        update_open_agb_config_text(CURRENT_CONFIG, {("system", "dangerousThing"): "1"})


def test_write_creates_backup_and_replaces_config_atomically(tmp_path: Path):
    config_dir = tmp_path / "3ds" / "open_agb_firm"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.ini"
    config_path.write_text(CURRENT_CONFIG, encoding="utf-8")

    result = write_open_agb_config(
        tmp_path,
        {("general", "useSavesFolder"): False, ("video", "colorProfile"): "gba"},
    )

    assert result == config_path
    assert "useSavesFolder=false" in config_path.read_text(encoding="utf-8")
    assert "colorProfile=gba" in config_path.read_text(encoding="utf-8")
    backup = config_path.with_name(config_path.name + BACKUP_SUFFIX)
    assert backup.read_text(encoding="utf-8") == CURRENT_CONFIG
    assert not config_path.with_name(config_path.name + ".rommheld.tmp").exists()


def test_missing_config_must_be_created_by_open_agb_firm_first(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Launch open_agb_firm once"):
        write_open_agb_config(tmp_path, {("general", "directBoot"): True})
