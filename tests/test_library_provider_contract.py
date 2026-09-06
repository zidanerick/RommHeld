from __future__ import annotations

import json
from pathlib import Path

import pytest

from romm_vita_manager.library_records import (
    LocalContentRef,
    RomMContentRef,
    library_item_from_local,
    library_item_from_romm,
)
from romm_vita_manager.models import Game
from romm_vita_manager.romm_library_cache import (
    _cache_path,
    load_cached_page,
    save_cached_page,
)
from romm_vita_manager.romm_remote import (
    RomMRemoteGame,
    download_artwork,
    list_3ds_games,
)
import romm_vita_manager.romm_remote as remote_module
import romm_vita_manager.romm_remote_worker as worker_module
from romm_vita_manager.romm_remote_worker import RomMLibraryWorker


def test_romm_mapping_preserves_exact_source_platform_identity(monkeypatch):
    responses = {
        "platforms": [{"id": 12, "name": "Nintendo 3DS", "slug": "3DS"}],
        "roms": {
            "items": [
                {
                    "id": 42,
                    "name": "Example",
                    "fs_name": "Example.3ds",
                    "platform_id": 12,
                    "size_bytes": 1234,
                }
            ]
        },
    }
    monkeypatch.setattr(
        remote_module,
        "_json_request",
        lambda instance_url, token, path, params=None: responses[path],
    )

    game = list_3ds_games("https://romm.example", "token")[0]

    assert game.rom_id == 42
    assert game.source_platform_id == 12
    assert game.source_platform_slug == "3DS"
    assert game.platform_slug == "3ds"
    assert game.platform == "Nintendo 3DS"


def test_normalized_library_item_keeps_source_and_display_identity_separate(tmp_path: Path):
    remote = RomMRemoteGame(
        7,
        "Portable Game",
        "portable.iso",
        "PlayStation Portable",
        2048,
        "https://romm.example/cover.jpg",
        "psp",
        "Sony",
        2005,
        source_platform_id=31,
        source_platform_slug="PSP",
    )
    remote_item = library_item_from_romm(remote)

    assert remote_item.provider == "romm"
    assert remote_item.provider_item_id == 7
    assert remote_item.platform.provider_platform_id == 31
    assert remote_item.platform.source_key == "PSP"
    assert remote_item.platform.canonical_key == "psp"
    assert remote_item.platform.display_name == "PlayStation Portable"
    assert remote_item.content_ref == RomMContentRef(7, "portable.iso")

    path = tmp_path / "games" / "example.nds"
    local = Game(path, "Example DS", "NDS", 4096, Path("NDS/example.nds"))
    local_item = library_item_from_local(local)

    assert local_item.provider == "local"
    assert local_item.platform.source_key == "NDS"
    assert local_item.platform.canonical_key == "nds"
    assert local_item.platform.display_name == "Nintendo DS"
    assert local_item.content_ref == LocalContentRef(path)


def test_romm_cache_v2_preserves_metadata_and_isolates_target_scope(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "romm_vita_manager.platform_services.cache_dir",
        lambda: tmp_path,
    )
    game = RomMRemoteGame(
        7,
        "Portable Game",
        "portable.iso",
        "PlayStation Portable",
        2048,
        "https://romm.example/cover.jpg",
        "psp",
        "Sony",
        2005,
        source_platform_id=31,
        source_platform_slug="PSP",
    )

    save_cached_page("https://romm.example", [game], scope_key="vita")

    cached = load_cached_page("https://romm.example", scope_key="vita")
    assert len(cached) == 1
    assert cached[0].publisher == "Sony"
    assert cached[0].release_year == 2005
    assert cached[0].source_platform_id == 31
    assert cached[0].source_platform_slug == "PSP"
    assert load_cached_page("https://romm.example", scope_key="3ds") == []


def test_romm_cache_v1_payload_is_not_reused(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "romm_vita_manager.platform_services.cache_dir",
        lambda: tmp_path,
    )
    path = _cache_path("https://romm.example", "", None, "3ds")
    path.write_text(json.dumps({"version": 1, "games": []}), encoding="utf-8")

    assert load_cached_page("https://romm.example", scope_key="3ds") == []


class _ArtworkResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size=-1):
        return b"image"


@pytest.mark.parametrize(
    ("target", "expects_auth"),
    [
        ("https://romm.example/assets/cover.jpg", True),
        ("https://romm.example:443/assets/cover.jpg", True),
        ("http://romm.example/assets/cover.jpg", False),
        ("https://romm.example:444/assets/cover.jpg", False),
        ("https://cdn.example/assets/cover.jpg", False),
    ],
)
def test_artwork_authorization_is_limited_to_exact_romm_origin(
    monkeypatch,
    target: str,
    expects_auth: bool,
):
    captured = []

    def fake_open(req, timeout=None):
        captured.append(req)
        return _ArtworkResponse()

    monkeypatch.setattr(remote_module._ROMM_OPENER, "open", fake_open)

    assert download_artwork("https://romm.example", "secret-token", target) == b"image"
    authorization = captured[0].get_header("Authorization")
    assert bool(authorization) is expects_auth


def test_generic_romm_worker_pages_through_large_platform_without_omissions(monkeypatch):
    platforms = [
        {"id": 1, "name": "PlayStation Portable", "slug": "psp", "rom_count": 5},
        {"id": 2, "name": "Game Boy Advance", "slug": "gba", "rom_count": 4},
        {"id": 3, "name": "PlayStation 2", "slug": "ps2", "rom_count": 50},
    ]
    datasets = {
        "psp": [f"psp-{index}" for index in range(5)],
        "gba": [f"gba-{index}" for index in range(4)],
    }

    monkeypatch.setattr(worker_module, "load_cached_page", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        worker_module,
        "_json_request",
        lambda instance_url, token, path, params=None: platforms,
    )

    def fake_list(
        instance_url,
        token,
        allowed_slugs,
        *,
        limit,
        offset,
        missing_message,
        platform_items,
        search_term,
        platform_slug,
    ):
        slug = next(iter(allowed_slugs))
        assert slug in datasets, "worker queried a platform outside its caller-supplied scope"
        return datasets[slug][offset : offset + limit]

    monkeypatch.setattr(worker_module, "_list_games_for_platform_slugs", fake_list)

    cursor = 0
    loaded = []
    for _ in range(10):
        worker = RomMLibraryWorker(
            "https://romm.example",
            "token",
            page_size=3,
            offset=cursor,
            allowed_platform_slugs={"psp", "gba"},
            scope_label="Vita deployment routes",
            scope_key="vita",
            platform_priority=("psp", "gba"),
        )
        batches = []
        worker.loaded.connect(lambda batch, batches=batches: batches.append(list(batch)))
        worker.run()
        assert len(batches) == 1
        loaded.extend(batches[0])
        cursor += worker.platforms_consumed
        if cursor >= worker.platforms_total:
            break

    assert loaded == datasets["psp"] + datasets["gba"]
    assert cursor >= worker.platforms_total


def test_generic_romm_worker_selected_platform_keeps_plain_rom_offset(monkeypatch):
    platforms = [{"id": 1, "name": "PlayStation Portable", "slug": "psp"}]
    dataset = [f"psp-{index}" for index in range(6)]
    offsets = []

    monkeypatch.setattr(worker_module, "load_cached_page", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        worker_module,
        "_json_request",
        lambda instance_url, token, path, params=None: platforms,
    )

    def fake_list(
        instance_url,
        token,
        allowed_slugs,
        *,
        limit,
        offset,
        missing_message,
        platform_items,
        search_term,
        platform_slug,
    ):
        offsets.append(offset)
        return dataset[offset : offset + limit]

    monkeypatch.setattr(worker_module, "_list_games_for_platform_slugs", fake_list)

    worker = RomMLibraryWorker(
        "https://romm.example",
        "token",
        page_size=2,
        offset=3,
        platform_slug="psp",
        allowed_platform_slugs={"psp"},
        scope_label="Vita deployment routes",
        scope_key="vita",
    )
    batches = []
    worker.loaded.connect(lambda batch: batches.append(list(batch)))
    worker.run()

    assert offsets == [3]
    assert batches == [["psp-3", "psp-4"]]
