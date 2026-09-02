#!/usr/bin/env python3
"""Fetch the Icons8 Color assets used by the handheld selector.

The application itself never fetches these assets at runtime. Run this script
when updating the bundled artwork or preparing a release, then commit the
resulting files under assets/handhelds/icons8/.
"""
from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "assets" / "handhelds" / "icons8"

ASSETS = {
    "3ds_console.png": "https://img.icons8.com/color/1200/3ds-console.jpg",
    "nintendo_ds.png": "https://img.icons8.com/color/1200/nintendo-ds.png",
    "playstation.png": "https://img.icons8.com/color/1200/playstation.png",
    "playstation_portable.png": "https://img.icons8.com/color/1200/playstation-portable.png",
}


def download(name: str, url: str) -> None:
    target = DEST / name
    request = Request(url, headers={"User-Agent": "RommHeld asset fetcher"})
    with urlopen(request, timeout=30) as response:
        data = response.read()
    if not data:
        raise RuntimeError(f"Empty response for {url}")
    target.write_bytes(data)
    print(f"Fetched {name} ({len(data)} bytes)")


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    for name, url in ASSETS.items():
        download(name, url)
    print(f"Bundled Icons8 assets in {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
