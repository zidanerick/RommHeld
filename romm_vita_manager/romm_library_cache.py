from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .platform_services import cache_dir
from .romm_remote import RomMRemoteGame

CACHE_VERSION = 1
MAX_ENTRIES = 24


def _cache_root() -> Path:
    path = cache_dir() / "romm-library"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_path(instance_url: str, search_term: str, platform_slug: str | None) -> Path:
    identity = "\x1f".join((instance_url.strip().rstrip("/"), search_term.strip().casefold(), (platform_slug or "").casefold()))
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return _cache_root() / f"{digest}.json"


def load_cached_page(
    instance_url: str,
    search_term: str = "",
    platform_slug: str | None = None,
) -> list[RomMRemoteGame]:
    path = _cache_path(instance_url, search_term, platform_slug)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    if payload.get("version") != CACHE_VERSION or not isinstance(payload.get("games"), list):
        return []
    try:
        return [
            RomMRemoteGame(
                int(item["rom_id"]),
                str(item["name"]),
                str(item["filename"]),
                str(item["platform"]),
                int(item["size"]),
                item.get("cover_url"),
                str(item.get("platform_slug") or ""),
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
) -> None:
    path = _cache_path(instance_url, search_term, platform_slug)
    payload = {
        "version": CACHE_VERSION,
        "games": [
            {
                "rom_id": game.rom_id,
                "name": game.name,
                "filename": game.filename,
                "platform": game.platform,
                "size": game.size,
                "cover_url": game.cover_url,
                "platform_slug": game.platform_slug,
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
