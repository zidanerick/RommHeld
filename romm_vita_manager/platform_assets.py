from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parent.parent / "assets" / "handhelds"


@dataclass(frozen=True)
class PlatformAssets:
    key: str
    name: str
    device_large: str
    device_small: str
    logo: str
    logo_dark: str
    hardware_color: str
    accent: str
    decorative_only: bool
    source_url: str
    license_note: str

    def path(self, kind: str) -> Path:
        return ASSET_ROOT / self.key / getattr(self, kind)


PLATFORM_ASSETS = {
    "vita": PlatformAssets(
        "playstation_vita", "PlayStation Vita", "device_large.svg", "device_small.svg", "logo.svg", "logo_dark.svg",
        "#111111", "#3b9cf5", True,
        "https://commons.wikimedia.org/wiki/File:PlayStation_Vita_logo.svg",
        "Logo source reviewed on Wikimedia Commons; page identifies the image as public domain for copyright purposes and separately notes trademark restrictions.",
    ),
    "3ds": PlatformAssets(
        "nintendo_3ds", "Nintendo 3DS", "device_large.svg", "device_small.svg", "logo.svg", "logo_dark.svg",
        "#25a6c9", "#d12228", True,
        "https://commons.wikimedia.org/wiki/File:Nintendo_3DS_logo.svg",
        "Logo source reviewed on Wikimedia Commons; page identifies the image as public domain for copyright purposes and separately notes trademark restrictions.",
    ),
    "ds": PlatformAssets(
        "nintendo_ds", "Nintendo DS", "device_large.svg", "device_small.svg", "logo.svg", "logo_dark.svg",
        "#dfe3e8", "#54b8ff", True,
        "https://commons.wikimedia.org/wiki/File:Nintendo_DS_Logo.svg",
        "Logo source reviewed on Wikimedia Commons; page identifies the image as public domain for copyright purposes and separately notes trademark restrictions.",
    ),
}


def get_platform_assets(key: str) -> PlatformAssets | None:
    return PLATFORM_ASSETS.get(key)
