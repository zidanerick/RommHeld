from __future__ import annotations

import http.client
import json
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request
from urllib.parse import quote, urlencode

from .mappings import platform_label
from .romm_api import RomMApiError, normalize_romm_url
from .three_ds_targets import RETROARCH_PLATFORM_SLUGS


@dataclass(frozen=True)
class RomMRemoteGame:
    rom_id: int
    name: str
    filename: str
    platform: str
    size: int
    cover_url: str | None = None
    platform_slug: str = ""


def _auth_headers(token: str, *, accept: str = "application/json") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token.strip()}",
        "Accept": accept,
        "User-Agent": "RommHeld",
    }


def _create_romm_connection(address, timeout=None, source_address=None):
    """Open RomM connections IPv4-first, then fall back to IPv6."""
    host, port = address
    errors: list[OSError] = []
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            infos = socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)
        except OSError as exc:
            errors.append(exc)
            continue
        for family_info, socktype, proto, _canonname, sockaddr in infos:
            sock = socket.socket(family_info, socktype, proto)
            try:
                if timeout is not None:
                    sock.settimeout(timeout)
                if source_address:
                    sock.bind(source_address)
                sock.connect(sockaddr)
                return sock
            except OSError as exc:
                errors.append(exc)
                sock.close()
    if errors:
        raise errors[-1]
    raise OSError(f"Unable to resolve {host}:{port}")


class _RomMHTTPConnection(http.client.HTTPConnection):
    _create_connection = staticmethod(_create_romm_connection)


class _RomMHTTPSConnection(http.client.HTTPSConnection):
    _create_connection = staticmethod(_create_romm_connection)


class _RomMHTTPHandler(request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_RomMHTTPConnection, req)


class _RomMHTTPSHandler(request.HTTPSHandler):
    def https_open(self, req):
        # HTTPSHandler's check_hostname attribute is not present on all Python
        # releases. Let HTTPSConnection retain its normal SSL hostname check.
        return self.do_open(
            _RomMHTTPSConnection,
            req,
            context=self._context,
        )


_ROMM_OPENER = request.build_opener(_RomMHTTPHandler(), _RomMHTTPSHandler())


def _json_request(instance_url: str, token: str, path: str, params: dict | None = None):
    base = normalize_romm_url(instance_url)
    query = f"?{urlencode(params, doseq=True)}" if params else ""
    req = request.Request(f"{base}/api/{path.lstrip('/')}{query}", headers=_auth_headers(token))
    try:
        with _ROMM_OPENER.open(req, timeout=15) as response:
            return json.load(response)
    except error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            pass
        suffix = f" {detail[:240]}" if detail else ""
        raise RomMApiError(f"RomM API returned HTTP {exc.code}.{suffix}", exc.code) from exc
    except (error.URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        raise RomMApiError(f"Unable to reach the RomM server: {reason}") from exc


def _items(payload) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def resolve_cover_url(instance_url: str, cover: str | None) -> str | None:
    """Resolve a RomM cover path using RomM's frontend resource base."""
    if not cover:
        return None
    value = str(cover).strip()
    if value.startswith(("http://", "https://")):
        return value
    base = normalize_romm_url(instance_url)
    value = value.lstrip("/")
    if value.startswith("assets/romm/resources/"):
        return f"{base}/{value}"
    return f"{base}/assets/romm/resources/{value}"


def _platform_name(item: dict) -> str:
    value = item.get("platform_name") or item.get("platform_display_name")
    if value:
        return str(value)
    platform = item.get("platform")
    if isinstance(platform, dict) and platform.get("name"):
        return str(platform["name"])
    slug = item.get("platform_slug") or item.get("slug")
    return platform_label(str(slug)) if slug else "Unknown platform"


def _platform_slug(item: dict, by_id: dict[int, str], by_name: dict[str, str]) -> str:
    value = item.get("platform_slug")
    if value:
        return str(value).lower()
    platform_id = item.get("platform_id")
    if isinstance(platform_id, int) and platform_id in by_id:
        return by_id[platform_id]
    nested = item.get("platform")
    if isinstance(nested, dict):
        value = nested.get("slug")
        if value:
            return str(value).lower()
        name = nested.get("name")
        if name and str(name).lower() in by_name:
            return by_name[str(name).lower()]
    name = item.get("platform_name") or item.get("platform_display_name")
    if name and str(name).lower() in by_name:
        return by_name[str(name).lower()]
    return ""


def _list_games_for_platform_slugs(
    instance_url: str,
    token: str,
    allowed_slugs: set[str] | frozenset[str],
    *,
    limit: int = 200,
    offset: int = 0,
    missing_message: str,
    platform_items: list[dict] | None = None,
    search_term: str = "",
    platform_slug: str | None = None,
) -> list[RomMRemoteGame]:
    if platform_items is None:
        platforms = _items(_json_request(instance_url, token, "platforms"))
        wanted = [
            item
            for item in platforms
            if isinstance(item, dict)
            and str(item.get("slug", "")).lower() in allowed_slugs
            and isinstance(item.get("id"), int)
        ]
    else:
        wanted = platform_items
    if platform_slug:
        wanted = [item for item in wanted if str(item.get("slug", "")).lower() == platform_slug.lower()]
    if not wanted:
        raise RomMApiError(missing_message)

    platform_ids = [item["id"] for item in wanted]
    by_id = {item["id"]: str(item.get("slug") or "").lower() for item in wanted}
    by_name = {
        str(item.get("name") or item.get("slug") or "").lower(): str(item.get("slug") or "").lower()
        for item in wanted
        if item.get("name") or item.get("slug")
    }
    names = {
        item["id"]: str(item.get("name") or item.get("slug") or "Unknown platform")
        for item in wanted
    }

    params = {
        "platform_ids": platform_ids,
        "limit": max(1, min(limit, 500)),
        "offset": max(0, offset),
        "with_total": False,
        "with_char_index": False,
        "with_filter_values": False,
        "with_rom_id_index": False,
        "group_by_meta_id": False,
    }
    if search_term.strip():
        params["search_term"] = search_term.strip()

    rows = _items(_json_request(instance_url, token, "roms", params))

    games: list[RomMRemoteGame] = []
    for item in rows:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int):
            continue
        slug = _platform_slug(item, by_id, by_name)
        if slug not in allowed_slugs:
            continue
        platform = names.get(item.get("platform_id"), _platform_name(item))
        filename = str(item.get("fs_name") or item.get("file_name") or item.get("name") or "")
        name = str(item.get("name") or filename)
        size = int(item.get("fs_size_bytes") or item.get("size_bytes") or item.get("size") or 0)
        cover = (
            item.get("path_cover_large")
            or item.get("path_cover_small")
            or item.get("url_cover")
            or item.get("cover_path")
            or item.get("cover_url")
        )
        games.append(
            RomMRemoteGame(
                item["id"],
                name,
                filename,
                platform,
                size,
                resolve_cover_url(instance_url, cover),
                slug,
            )
        )
    return games


def list_compatible_games(instance_url: str, token: str, *, limit: int = 200) -> list[RomMRemoteGame]:
    return _list_games_for_platform_slugs(
        instance_url,
        token,
        RETROARCH_PLATFORM_SLUGS,
        limit=limit,
        offset=0,
        missing_message="RomM has no platforms currently recognised as compatible with the 3DS targets.",
    )


def list_3ds_games(instance_url: str, token: str, *, limit: int = 200) -> list[RomMRemoteGame]:
    games = _list_games_for_platform_slugs(
        instance_url,
        token,
        {"3ds"},
        limit=limit,
        offset=0,
        missing_message="RomM has no Nintendo 3DS platform (slug: 3ds).",
    )
    return [
        RomMRemoteGame(game.rom_id, game.name, game.filename, game.platform, game.size, game.cover_url)
        for game in games
    ]


def _download(instance_url: str, token: str, rom: RomMRemoteGame, destination: Path) -> Path:
    base = normalize_romm_url(instance_url)
    url = f"{base}/api/roms/{rom.rom_id}/content/{quote(rom.filename, safe='')}"
    destination = destination.expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with (
            _ROMM_OPENER.open(request.Request(url, headers=_auth_headers(token)), timeout=30)
            as response,
            destination.open("wb") as target,
        ):
            while chunk := response.read(1024 * 1024):
                target.write(chunk)
    except error.HTTPError as exc:
        raise RomMApiError(f"RomM ROM download returned HTTP {exc.code}.", exc.code) from exc
    except (error.URLError, TimeoutError) as exc:
        raise RomMApiError(f"Unable to download from RomM: {getattr(exc, 'reason', exc)}") from exc
    return destination


def download_rom(instance_url: str, token: str, rom: RomMRemoteGame, destination: Path) -> Path:
    return _download(instance_url, token, rom, destination)
