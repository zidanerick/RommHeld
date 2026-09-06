from __future__ import annotations

from romm_vita_manager.romm_remote import RomMRemoteGame
import romm_vita_manager.romm_remote_worker as worker_module
from romm_vita_manager.romm_remote_worker import RomMLibraryWorker


def test_cached_games_seed_platform_options_before_live_platform_request(monkeypatch):
    cached = [
        RomMRemoteGame(
            1,
            "Metroid Fusion",
            "Metroid Fusion.gba",
            "Game Boy Advance",
            8,
            None,
            "gba",
        ),
        RomMRemoteGame(
            2,
            "Pokémon Emerald",
            "Pokemon Emerald.gba",
            "Game Boy Advance",
            8,
            None,
            "gba",
        ),
    ]
    monkeypatch.setattr(worker_module, "load_cached_page", lambda *_args, **_kwargs: cached)

    worker = RomMLibraryWorker("https://romm.example", "token")

    assert worker._cached_platform_options() == [
        {"slug": "gba", "name": "Game Boy Advance"}
    ]


def test_cached_platform_seed_ignores_non_3ds_compatible_slugs(monkeypatch):
    cached = [
        RomMRemoteGame(1, "Supported", "game.gba", "Game Boy Advance", 8, None, "gba"),
        RomMRemoteGame(2, "Unsupported", "game.xyz", "Unknown System", 8, None, "not-a-target"),
    ]
    monkeypatch.setattr(worker_module, "load_cached_page", lambda *_args, **_kwargs: cached)

    worker = RomMLibraryWorker("https://romm.example", "token")

    assert worker._cached_platform_options() == [
        {"slug": "gba", "name": "Game Boy Advance"}
    ]
