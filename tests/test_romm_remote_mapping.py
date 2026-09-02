from romm_vita_manager.romm_remote import list_3ds_games


def test_list_3ds_games_uses_nested_platform_name(monkeypatch):
    responses = {
        "platforms": [{"id": 12, "slug": "3ds", "name": "Nintendo 3DS"}],
        "roms": {"items": [{"id": 1, "name": "Test", "fs_name": "Test.3ds", "platform": {"name": "Nintendo 3DS"}, "size_bytes": 123}]},
    }
    monkeypatch.setattr("romm_vita_manager.romm_remote._json_request", lambda instance_url, token, path, params=None: responses[path])
    games = list_3ds_games("https://romm.example", "rmm_test")
    assert games[0].platform == "Nintendo 3DS"
