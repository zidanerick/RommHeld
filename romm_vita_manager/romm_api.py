from __future__ import annotations

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
        with request.urlopen(req, timeout=10) as response:
            import json

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
