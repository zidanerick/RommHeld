from __future__ import annotations

from romm_vita_manager.romm_remote import RomMRemoteGame, list_3ds_games


def test_list_3ds_games_accepts_platform_object(monkeypatch):
    responses = {
        "platforms": [{"id": 12, "name": "Nintendo 3DS", "slug": "3ds"}],
        "roms": {"items": [{"id": 42, "name": "Test", "fs_name": "Test.3ds", "platform": {"name": "Nintendo 3DS"}, "size_bytes": 123}]},
    }
    monkeypatch.setattr("romm_vita_manager.romm_remote._json_request", lambda *args, **kwargs: responses[args[2]])
    games = list_3ds_games("https://romm.example", "rmm_test")
    assert games[0].platform == "Nintendo 3DS"
