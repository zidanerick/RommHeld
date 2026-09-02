from __future__ import annotations

from pathlib import Path

from romm_vita_manager.romm import scan_games


def test_scan_games_includes_3ds_package_formats(tmp_path: Path):
    platform_root = tmp_path / "3ds"
    platform_root.mkdir()
    (platform_root / "Example.3ds").write_bytes(b"3ds")
    (platform_root / "Example.3dsx").write_bytes(b"3dsx")
    (platform_root / "Example.cia").write_bytes(b"cia")

    games = scan_games(tmp_path)

    assert {game.path.suffix.lower() for game in games} == {".3ds", ".3dsx", ".cia"}
    assert {game.source_platform for game in games} == {"3ds"}
