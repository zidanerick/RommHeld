from __future__ import annotations

import threading
from pathlib import Path

import pytest

from romm_vita_manager.romm_remote import (
    RomMRemoteGame,
    _create_romm_connection,
    _download,
    list_3ds_games,
    list_compatible_games,
    resolve_cover_url,
)


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
                    "path_cover_large": "roms/12/42/cover.jpg",
                }
            ]
        },
    }

    monkeypatch.setattr(
        "romm_vita_manager.romm_remote._json_request",
        lambda instance_url, token, path, params=None: responses[path],
    )
    games = list_3ds_games("https://romm.example", "rmm_test")

    assert games == [
        RomMRemoteGame(
            42,
            "Pokémon Alpha Sapphire",
            "Pokemon Alpha Sapphire.3ds",
            "Nintendo 3DS",
            1234,
            "https://romm.example/assets/romm/resources/roms/12/42/cover.jpg",
            "3ds",
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
        assert "Nintendo 3DS platform" in str(exc)
    else:
        raise AssertionError("Expected a RomMApiError")


def test_list_compatible_games_maps_dedicated_runtime_platforms_and_skips_unknown(monkeypatch):
    responses = {
        "platforms": [
            {"id": 10, "name": "Game Boy Advance", "slug": "gba"},
            {"id": 20, "name": "Nintendo DS", "slug": "nds"},
            {"id": 30, "name": "PlayStation 2", "slug": "ps2"},
        ],
        "roms": {
            "items": [
                {
                    "id": 7,
                    "name": "Metroid Fusion",
                    "fs_name": "Metroid Fusion.gba",
                    "platform_id": 10,
                    "fs_size_bytes": 4194304,
                    "path_cover_large": "roms/10/7/cover.jpg",
                },
                {
                    "id": 8,
                    "name": "Example DS game",
                    "fs_name": "example.nds",
                    "platform_id": 20,
                    "size_bytes": 9000,
                },
                {
                    "id": 9,
                    "name": "Unsupported PS2 game",
                    "fs_name": "unsupported.iso",
                    "platform_id": 30,
                    "size_bytes": 12345,
                },
            ]
        },
    }

    monkeypatch.setattr(
        "romm_vita_manager.romm_remote._json_request",
        lambda instance_url, token, path, params=None: responses[path],
    )

    games = list_compatible_games("https://romm.example", "rmm_test")

    assert games == [
        RomMRemoteGame(
            7,
            "Metroid Fusion",
            "Metroid Fusion.gba",
            "Game Boy Advance",
            4194304,
            "https://romm.example/assets/romm/resources/roms/10/7/cover.jpg",
            "gba",
        ),
        RomMRemoteGame(
            8,
            "Example DS game",
            "example.nds",
            "Nintendo DS",
            9000,
            None,
            "nds",
        ),
    ]


def test_resolve_cover_url_preserves_absolute_urls():
    assert (
        resolve_cover_url("https://romm.example", "https://cdn.example/cover.jpg")
        == "https://cdn.example/cover.jpg"
    )
    assert (
        resolve_cover_url(
            "https://romm.example",
            "/assets/romm/resources/cover.jpg",
        )
        == "https://romm.example/assets/romm/resources/cover.jpg"
    )


def test_download_streams_to_destination_atomically(monkeypatch, tmp_path: Path):
    class FakeResponse:
        headers = {"Content-Length": "8"}

        def __init__(self):
            self.done = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, size=-1):
            if self.done:
                return b""
            self.done = True
            return b"rom-data"

    monkeypatch.setattr(
        "romm_vita_manager.romm_remote._ROMM_OPENER.open",
        lambda *args, **kwargs: FakeResponse(),
    )
    game = RomMRemoteGame(7, "Test", "test.gba", "Game Boy Advance", 8)
    destination = tmp_path / "test.gba"
    progress = []

    result = _download(
        "https://romm.example",
        "rmm_test",
        game,
        destination,
        progress=lambda done, total: progress.append((done, total)),
    )

    assert result == destination
    assert destination.read_bytes() == b"rom-data"
    assert progress == [(8, 8)]
    assert not destination.with_name(destination.name + ".rommheld.part").exists()


def test_cancelled_download_preserves_existing_destination_and_cleans_partial(monkeypatch, tmp_path: Path):
    cancel = threading.Event()

    class FakeResponse:
        headers = {"Content-Length": str(2 * 1024 * 1024)}

        def __init__(self):
            self.reads = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, size=-1):
            self.reads += 1
            if self.reads == 1:
                return b"x" * (1024 * 1024)
            return b"y" * (1024 * 1024)

    monkeypatch.setattr(
        "romm_vita_manager.romm_remote._ROMM_OPENER.open",
        lambda *args, **kwargs: FakeResponse(),
    )
    game = RomMRemoteGame(7, "Test", "test.gba", "Game Boy Advance", 2 * 1024 * 1024)
    destination = tmp_path / "test.gba"
    destination.write_bytes(b"existing")

    with pytest.raises(InterruptedError, match="cancelled"):
        _download(
            "https://romm.example",
            "rmm_test",
            game,
            destination,
            cancel_event=cancel,
            progress=lambda _done, _total: cancel.set(),
        )

    assert destination.read_bytes() == b"existing"
    assert not destination.with_name(destination.name + ".rommheld.part").exists()


def test_pre_cancelled_download_does_not_open_network_or_touch_destination(monkeypatch, tmp_path: Path):
    cancel = threading.Event()
    cancel.set()
    monkeypatch.setattr(
        "romm_vita_manager.romm_remote._ROMM_OPENER.open",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network should not open")),
    )
    game = RomMRemoteGame(7, "Test", "test.gba", "Game Boy Advance", 8)
    destination = tmp_path / "test.gba"
    destination.write_bytes(b"existing")

    with pytest.raises(InterruptedError, match="cancelled"):
        _download(
            "https://romm.example",
            "rmm_test",
            game,
            destination,
            cancel_event=cancel,
        )

    assert destination.read_bytes() == b"existing"


def test_romm_connection_prefers_ipv4(monkeypatch):
    attempts = []

    class FakeSocket:
        def __init__(self, family, socktype, proto):
            self.family = family
            self.socktype = socktype
            self.proto = proto

        def settimeout(self, timeout):
            pass

        def connect(self, sockaddr):
            attempts.append((self.family, sockaddr))
            if self.family == 2:
                return
            raise OSError("IPv6 unavailable")

        def close(self):
            pass

    monkeypatch.setattr(
        "romm_vita_manager.romm_remote.socket.getaddrinfo",
        lambda host, port, family, socktype: [
            (family, socktype, 6, "", ("127.0.0.1", port))
        ],
    )
    monkeypatch.setattr("romm_vita_manager.romm_remote.socket.socket", FakeSocket)

    sock = _create_romm_connection(("games.example", 443), timeout=1)

    assert sock.family == 2
    assert attempts == [(2, ("127.0.0.1", 443))]
