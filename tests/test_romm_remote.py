from __future__ import annotations

from pathlib import Path

from romm_vita_manager.romm_remote import RomMRemoteGame, _download, list_3ds_games


def test_list_3ds_games_maps_platform_and_rom_fields(monkeypatch):
    responses = {
        "platforms": [
            {"id": 12, "name": "Nintendo 3DS", "slug": "3ds"},
            {"id": 3, "name": "Nintendo DS", "slug": "nds"},
        ],
        "roms": {
            "items": [
                {
                    "id": 42,
                    "name": "Pokémon Alpha Sapphire",
                    "fs_name": "Pokemon Alpha Sapphire.3ds",
                    "platform_name": "Nintendo 3DS",
                    "size_bytes": 1234,
                    "cover_path": "/assets/covers/42.jpg",
                }
            ]
        },
    }

    def fake_request(instance_url, token, path, params=None):
        return responses[path]

    monkeypatch.setattr("romm_vita_manager.romm_remote._json_request", fake_request)
    games = list_3ds_games("https://romm.example", "rmm_test")

    assert games == [
        RomMRemoteGame(
            42,
            "Pokémon Alpha Sapphire",
            "Pokemon Alpha Sapphire.3ds",
            "Nintendo 3DS",
            1234,
            "/assets/covers/42.jpg",
        )
    ]


def test_list_3ds_games_requires_the_3ds_platform(monkeypatch):
    monkeypatch.setattr(
        "romm_vita_manager.romm_remote._json_request",
        lambda *args, **kwargs: [{"id": 1, "name": "Nintendo DS", "slug": "nds"}],
    )

    try:
        list_3ds_games("https://romm.example", "rmm_test")
    except Exception as exc:
        assert "slug: 3ds" in str(exc)
    else:
        raise AssertionError("Expected a RomMApiError")


def test_download_streams_to_destination(monkeypatch, tmp_path: Path):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, size=-1):
            if self.done:
                return b""
            self.done = True
            return b"rom-data"

        done = False

    monkeypatch.setattr(
        "romm_vita_manager.romm_remote.request.urlopen",
        lambda *args, **kwargs: FakeResponse(),
    )
    game = RomMRemoteGame(7, "Test", "test.gba", "Game Boy Advance", 8)
    destination = tmp_path / "test.gba"

    result = _download("https://romm.example", "rmm_test", game, destination)

    assert result == destination
    assert destination.read_bytes() == b"rom-data"
