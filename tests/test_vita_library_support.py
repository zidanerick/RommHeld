from pathlib import Path

from romm_vita_manager.models import Game
from romm_vita_manager.vita_library_support import (
    destination_for_game,
    destination_target,
)


def _game(path: Path, platform: str, name: str | None = None) -> Game:
    return Game(
        path=path,
        name=name or path.stem,
        source_platform=platform,
        size=123,
        relative=Path(platform) / path.name,
    )


def test_psp_iso_and_cso_route_to_adrenaline_iso(tmp_path: Path):
    for filename in ("Ridge Racer.iso", "Lumines.cso"):
        game = _game(Path("/library/psp") / filename, "psp")
        label, target, mode = destination_target(tmp_path, game, {})

        assert label == "PSP / Adrenaline ISO"
        assert mode == "file"
        assert target == tmp_path / "pspemu" / "ISO" / filename


def test_psp_pbp_routes_to_adrenaline_game_folder(tmp_path: Path):
    game = _game(Path("/library/psp/LocoRoco.pbp"), "psp")

    label, target, mode = destination_target(tmp_path, game, {})

    assert label == "PSP / Adrenaline GAME"
    assert mode == "game-folder"
    assert target == tmp_path / "pspemu" / "PSP" / "GAME" / "LocoRoco" / "EBOOT.PBP"


def test_existing_eboot_uses_source_parent_as_game_folder(tmp_path: Path):
    game = _game(Path("/library/psp/Patapon/EBOOT.PBP"), "psp")

    _label, target, mode = destination_target(tmp_path, game, {})

    assert mode == "game-folder"
    assert target == tmp_path / "pspemu" / "PSP" / "GAME" / "Patapon" / "EBOOT.PBP"


def test_ps1_pbp_routes_to_adrenaline_game_folder(tmp_path: Path):
    game = _game(Path("/library/psx/Symphony of the Night.pbp"), "psx")

    label, target, mode = destination_target(tmp_path, game, {})

    assert label == "PS1 / Adrenaline GAME"
    assert mode == "game-folder"
    assert target == (
        tmp_path
        / "pspemu"
        / "PSP"
        / "GAME"
        / "Symphony of the Night"
        / "EBOOT.PBP"
    )


def test_ps1_non_pbp_formats_are_not_silently_renamed(tmp_path: Path):
    for filename in ("Final Fantasy VII.cue", "Final Fantasy VII.bin", "Tekken 3.chd"):
        game = _game(Path("/library/psx") / filename, "psx")
        label, _destination, mode = destination_for_game(tmp_path, game, {})

        assert label == "PS1 requires an EBOOT.PBP for Adrenaline"
        assert mode == "unknown"


def test_psp_unknown_formats_require_destination_review(tmp_path: Path):
    game = _game(Path("/library/psp/archive.zip"), "psp")

    label, _destination, mode = destination_for_game(tmp_path, game, {})

    assert label == "PSP requires ISO/CSO or EBOOT.PBP"
    assert mode == "unknown"
