from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request
from urllib.parse import quote, urlencode

from .romm_api import RomMApiError, normalize_romm_url


@dataclass(frozen=True)
class RomMRemoteGame:
    rom_id: int
    name: str
    filename: str
    platform: str
    size: int
    cover_url: str | None = None


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token.strip()}", "Accept": "application/json", "User-Agent": "RommHeld"}


def _json_request(instance_url: str, token: str, path: str, params: dict | None = None):
    base = normalize_romm_url(instance_url)
    query = f"?{urlencode(params, doseq=True)}" if params else ""
    req = request.Request(f"{base}/api/{path.lstrip('/')}{query}", headers=_auth_headers(token))
    try:
        with request.urlopen(req, timeout=15) as response:
            return json.load(response)
    except error.HTTPError as exc:
        detail = ""
        try: detail = exc.read().decode("utf-8", errors="replace").strip()
        except Exception: pass
        suffix = f" {detail[:240]}" if detail else ""
        raise RomMApiError(f"RomM API returned HTTP {exc.code}.{suffix}", exc.code) from exc
    except (error.URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        raise RomMApiError(f"Unable to reach the RomM server: {reason}") from exc


def _items(payload):
    if isinstance(payload, list): return payload
    if isinstance(payload, dict):
        for key in ("items", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list): return value
    return []


def _download(instance_url: str, token: str, rom: RomMRemoteGame, destination: Path) -> Path:
    base = normalize_romm_url(instance_url)
    url = f"{base}/api/roms/{rom.rom_id}/content/{quote(rom.filename, safe='')}"
    destination = destination.expanduser(); destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with request.urlopen(request.Request(url, headers=_auth_headers(token)), timeout=30) as response, destination.open("wb") as target:
            while chunk := response.read(1024 * 1024): target.write(chunk)
    except error.HTTPError as exc:
        raise RomMApiError(f"RomM ROM download returned HTTP {exc.code}.", exc.code) from exc
    except (error.URLError, TimeoutError) as exc:
        raise RomMApiError(f"Unable to download from RomM: {getattr(exc, 'reason', exc)}") from exc
    return destination


def _platform_name(item: dict) -> str:
    value = item.get("platform_name")
    if value: return str(value)
    platform = item.get("platform")
    if isinstance(platform, dict) and platform.get("name"): return str(platform["name"])
    return "Nintendo 3DS"


def list_3ds_games(instance_url: str, token: str, *, limit: int = 1000) -> list[RomMRemoteGame]:
    platforms = _items(_json_request(instance_url, token, "platforms"))
    platform_ids = [item["id"] for item in platforms if isinstance(item, dict) and str(item.get("slug", "")).lower() == "3ds" and isinstance(item.get("id"), int)]
    if not platform_ids: raise RomMApiError("RomM has no Nintendo 3DS platform (slug: 3ds).")
    rows = _items(_json_request(instance_url, token, "roms", {"platform_ids": platform_ids, "limit": limit, "offset": 0, "with_total": False}))
    games=[]
    for item in rows:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int): continue
        filename=str(item.get("fs_name") or item.get("file_name") or item.get("name") or "")
        name=str(item.get("name") or filename)
        size=int(item.get("size_bytes") or item.get("size") or 0)
        cover=item.get("cover_path") or item.get("cover_url")
        games.append(RomMRemoteGame(item["id"], name, filename, _platform_name(item), size, str(cover) if cover else None))
    return games


def download_rom(instance_url: str, token: str, rom: RomMRemoteGame, destination: Path) -> Path:
    return _download(instance_url, token, rom, destination)
