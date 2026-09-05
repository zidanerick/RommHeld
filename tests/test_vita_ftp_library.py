from pathlib import Path

from romm_vita_manager.models import Game
from romm_vita_manager.vita_ftp_library import ftp_destination_target


def game(path: str, platform: str, name: str = "Game") -> Game:
    source = Path(path)
    return Game(
        path=source,
        name=name,
        source_platform=platform,
        size=123,
        relative=source,
    )


def test_ftp_destination_reuses_retroflow_mapping():
    label, target, mode = ftp_destination_target(
        game("title.sfc", "snes"),
        {"snes": "SNES"},
    )
    assert label == "RetroFlow / SNES"
    assert target == "ux0:/data/RetroFlow/ROMS/SNES/title.sfc"
    assert mode == "file"


def test_ftp_destination_reuses_adrenaline_iso_mapping():
    label, target, mode = ftp_destination_target(game("title.iso", "psp"), {})
    assert label == "PSP / Adrenaline ISO"
    assert target == "ux0:/pspemu/ISO/title.iso"
    assert mode == "file"


def test_ftp_destination_preserves_eboot_folder_name():
    label, target, mode = ftp_destination_target(
        game("SLUS01234/EBOOT.PBP", "ps1", "Friendly Name"),
        {},
    )
    assert label == "PS1 / Adrenaline GAME"
    assert target == "ux0:/pspemu/PSP/GAME/SLUS01234/EBOOT.PBP"
    assert mode == "game-folder"


def test_ftp_destination_rejects_unknown_mapping():
    _label, target, mode = ftp_destination_target(game("title.bin", "unknown"), {})
    assert target == ""
    assert mode == "unknown"
