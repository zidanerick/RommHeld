from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .romm_remote import RomMRemoteGame

CACHE_VERSION = 2
MAX_ENTRIES = 24


def _cache_root() -> Path:
    # Keep the cache module importable by headless tests without importing Qt.
    from .platform_services import cache_dir

    path = cache_dir() / "romm-library"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_path(
    instance_url: str,
    search_term: str,
    platform_slug: str | None,
    scope_key: str = "3ds",
) -> Path:
    identity = "\x1f".join(
        (
            instance_url.strip().rstrip("/"),
            str(scope_key or "default").strip().casefold(),
            search_term.strip().casefold(),
            (platform_slug or "").casefold(),
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return _cache_root() / f"{digest}.json"


def load_cached_page(
    instance_url: str,
    search_term: str = "",
    platform_slug: str | None = None,
    *,
    scope_key: str = "3ds",
) -> list[RomMRemoteGame]:
    path = _cache_path(instance_url, search_term, platform_slug, scope_key)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    if payload.get("version") != CACHE_VERSION or not isinstance(payload.get("games"), list):
        return []
    try:
        return [
            RomMRemoteGame(
                rom_id=int(item["rom_id"]),
                name=str(item["name"]),
                filename=str(item["filename"]),
                platform=str(item["platform"]),
                size=int(item["size"]),
                cover_url=item.get("cover_url"),
                platform_slug=str(item.get("platform_slug") or ""),
                publisher=str(item.get("publisher") or ""),
                release_year=(
                    int(item["release_year"])
                    if item.get("release_year") is not None
                    else None
                ),
                source_platform_id=(
                    int(item["source_platform_id"])
                    if item.get("source_platform_id") is not None
                    else None
                ),
                source_platform_slug=str(item.get("source_platform_slug") or ""),
            )
            for item in payload["games"][:MAX_ENTRIES]
        ]
    except (KeyError, TypeError, ValueError):
        return []


def save_cached_page(
    instance_url: str,
    games: list[RomMRemoteGame],
    search_term: str = "",
    platform_slug: str | None = None,
    *,
    scope_key: str = "3ds",
) -> None:
    path = _cache_path(instance_url, search_term, platform_slug, scope_key)
    payload = {
        "version": CACHE_VERSION,
        "scope_key": str(scope_key or "default").strip().casefold(),
        "games": [
            {
                "rom_id": game.rom_id,
                "name": game.name,
                "filename": game.filename,
                "platform": game.platform,
                "size": game.size,
                "cover_url": game.cover_url,
                "platform_slug": game.platform_slug,
                "publisher": game.publisher,
                "release_year": game.release_year,
                "source_platform_id": game.source_platform_id,
                "source_platform_slug": game.source_platform_slug,
            }
            for game in games[:MAX_ENTRIES]
        ],
    }
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
