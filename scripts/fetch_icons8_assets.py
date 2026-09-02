#!/usr/bin/env python3
"""Vendor the Icons8 artwork used by the handheld selector.

Run this script when preparing a checkout/release that should contain the
artwork locally. RommHeld does not fetch artwork from the network at runtime.
"""
from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "assets" / "handhelds" / "icons8"

ASSETS = {
    "vita.png": "https://img.icons8.com/color/96/playstation.png",
    "3ds.png": "https://img.icons8.com/color/96/3ds-console.png",
    "ds.png": "https://img.icons8.com/color/96/nintendo-ds.png",
    "psp.png": "https://img.icons8.com/color/96/playstation-portable.png",
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
    print(f"Icons8 assets are ready in: {DEST}")
    print("Review and commit the generated files before packaging a release.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
