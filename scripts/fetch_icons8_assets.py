#!/usr/bin/env python3
"""Prepare the Icons8 artwork used by the handheld selector.

Run this script when preparing a local checkout or release bundle. The
application itself never fetches artwork from the network at runtime.

Icons8 currently exposes the Color assets used here at 100px. The source pages
also provide the download options and attribution requirements recorded in
``docs/ASSET_SOURCES.md``.
"""
from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "assets" / "handhelds" / "icons8"

# These correspond to the current page-rendered Color assets. Icons8's Color
# pages advertise PNG output up to 100px, while these individual rendered
# assets are exposed by the site as JPGs.
ASSETS = {
    "vita.jpg": "https://img.icons8.com/color/100/playstation.jpg",
    "3ds.jpg": "https://img.icons8.com/color/100/3ds-console.jpg",
    "ds.jpg": "https://img.icons8.com/color/100/nintendo-ds.jpg",
    "psp.jpg": "https://img.icons8.com/color/100/playstation-portable.jpg",
}


def download(name: str, url: str) -> bool:
    target = DEST / name
    request = Request(url, headers={"User-Agent": "RommHeld asset preparation"})
    try:
        with urlopen(request, timeout=30) as response:
            data = response.read()
    except HTTPError as exc:
        print(f"FAILED {name}: HTTP {exc.code} from {url}")
        return False
    except URLError as exc:
        print(f"FAILED {name}: network error: {exc.reason}")
        return False

    if not data:
        print(f"FAILED {name}: empty response")
        return False

    target.write_bytes(data)
    print(f"Fetched {name} ({len(data)} bytes)")
    return True


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    failures = 0
    for name, url in ASSETS.items():
        if not download(name, url):
            failures += 1

    if failures:
        print(f"\n{failures} Icons8 asset(s) could not be prepared.")
        print("Review the source URLs in this script before packaging a release.")
        return 1

    print(f"\nIcons8 assets are ready in: {DEST}")
    print("RommHeld does not fetch these assets at runtime.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
