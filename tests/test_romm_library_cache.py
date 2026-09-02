from __future__ import annotations

from pathlib import Path

from romm_vita_manager.romm_library_cache import load_cached_page, save_cached_page
from romm_vita_manager.romm_remote import RomMRemoteGame


def test_romm_library_cache_round_trip(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "romm_vita_manager.platform_services.cache_dir",
        lambda: tmp_path,
    )
    games = [
        RomMRemoteGame(
            42,
            "Pokémon Alpha Sapphire",
            "Pokemon Alpha Sapphire.3ds",
            "Nintendo 3DS",
            1234,
            "https://romm.example/assets/cover.jpg",
            "3ds",
        )
    ]

    save_cached_page("https://romm.example", games)

    assert load_cached_page("https://romm.example") == games


def test_romm_library_cache_is_scoped_by_search_and_platform(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "romm_vita_manager.platform_services.cache_dir",
        lambda: tmp_path,
    )
    gba = RomMRemoteGame(1, "Metroid Fusion", "Metroid Fusion.gba", "Game Boy Advance", 8, None, "gba")
    ds = RomMRemoteGame(2, "Metroid Prime Hunters", "Metroid Prime Hunters.nds", "Nintendo DS", 8, None, "nds")

    save_cached_page("https://romm.example", [gba], "metroid", "gba")
    save_cached_page("https://romm.example", [ds], "metroid", "nds")

    assert load_cached_page("https://romm.example", "metroid", "gba") == [gba]
    assert load_cached_page("https://romm.example", "metroid", "nds") == [ds]
