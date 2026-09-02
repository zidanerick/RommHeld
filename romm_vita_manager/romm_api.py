from __future__ import annotations

import http.client
import json
import socket
from dataclasses import dataclass
from urllib import error, request
from urllib.parse import urlparse, urlunparse


class RomMApiError(RuntimeError):
    """Structured error from a RomM API request."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def normalize_romm_url(value: str) -> str:
    """Normalize a RomM instance URL or API base URL to its instance root."""
    raw = value.strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("RomM URL must include http:// or https:// and a hostname.")

    path = parsed.path.rstrip("/")
    if path == "/api":
        path = ""
    elif path.endswith("/api"):
        path = path[:-4].rstrip("/")

    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


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


class _RomMHTTPSConnection(http.client.HTTPSConnection):
    _create_connection = staticmethod(_create_romm_connection)


class _RomMHTTPSHandler(request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(
            _RomMHTTPSConnection,
            req,
            context=self._context,
        )


_ROMM_OPENER = request.build_opener(_RomMHTTPSHandler())


def _request_json(instance_url: str, token: str, path: str):
    base = normalize_romm_url(instance_url)
    endpoint = f"{base}/api/{path.lstrip('/')}"
    req = request.Request(
        endpoint,
        headers={
            "Authorization": f"Bearer {token.strip()}",
            "Accept": "application/json",
            "User-Agent": "RommHeld",
        },
    )
    try:
        with _ROMM_OPENER.open(req, timeout=10) as response:
            return json.load(response)
    except error.HTTPError as exc:
        if exc.code == 401:
            raise RomMApiError("RomM rejected the token (401). Check that the Client API Token is valid.", 401) from exc
        if exc.code == 403:
            raise RomMApiError(
                "RomM accepted the token but denied this request (403). The Client API Token needs the required scope, typically platforms.read for platform discovery.",
                403,
            ) from exc
        raise RomMApiError(f"RomM API returned HTTP {exc.code}.", exc.code) from exc
    except (error.URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        raise RomMApiError(f"Unable to reach the RomM server: {reason}") from exc


def test_connection(instance_url: str, token: str) -> None:
    if not token.strip():
        raise ValueError("Enter a Client API Token.")
    if not token.strip().startswith("rmm_"):
        raise ValueError("This field expects a RomM Client API Token beginning with rmm_.")
    _request_json(instance_url, token, "platforms")


@dataclass(frozen=True)
class RomMApiClient:
    instance_url: str
    token: str

    def get_platforms(self):
        return _request_json(self.instance_url, self.token, "platforms")
