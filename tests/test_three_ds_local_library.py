from pathlib import Path

from romm_vita_manager.models import Game
from romm_vita_manager.romm import scan_games
from romm_vita_manager.three_ds_library import _local_platform_slug, _local_targets


def _game(tmp_path: Path, platform: str, filename: str) -> Game:
    path = tmp_path / platform / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"rom")
    return Game(path, path.stem, platform, path.stat().st_size, path.relative_to(tmp_path))


def test_local_platform_slug_accepts_romm_slug_and_display_label():
    assert _local_platform_slug("gba") == "gba"
    assert _local_platform_slug("Game Boy Advance") == "gba"
    assert _local_platform_slug("Nintendo 64") == "n64"


def test_local_library_exposes_only_existing_file_routes(tmp_path: Path):
    gba = _game(tmp_path, "gba", "Metroid.gba")
    gb = _game(tmp_path, "gb", "Tetris.gb")
    cia = _game(tmp_path, "3ds", "Homebrew.cia")
    three_dsx = _game(tmp_path, "3ds", "Homebrew.3dsx")

    assert [target.key for target in _local_targets(gba)] == [
        "open_agb_firm",
        "retroarch",
    ]
    assert [target.key for target in _local_targets(gb)] == ["retroarch"]
    assert [target.key for target in _local_targets(cia)] == ["native_3ds_cia"]
    assert _local_targets(three_dsx) == ()


def test_local_scan_recognizes_dedicated_and_retroarch_formats(tmp_path: Path):
    expected = {
        "virtualboy": "Wario.vb",
        "wonderswan": "Gunpey.ws",
        "neo-geo-pocket": "Sonic.ngp",
        "vectrex": "Minestorm.vec",
        "c64": "Game.d64",
        "amiga": "Game.adf",
    }
    for platform, filename in expected.items():
        path = tmp_path / platform / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"rom")

    games = scan_games(tmp_path)
    found = {(game.source_platform, game.path.name) for game in games}
    assert found == set(expected.items())


def test_main_3ds_library_reuses_verified_transfer_worker():
    source = (Path(__file__).parents[1] / "romm_vita_manager" / "three_ds_library.py").read_text(
        encoding="utf-8"
    )

    assert "ThreeDSTransferWorker" in source
    assert "worker = ThreeDSTransferWorker(" in source
    assert "PACKAGE_GENERATION_TARGETS" in source
    assert "scan_games(root)" in source
    assert "Open Device → Connection setup" in source
