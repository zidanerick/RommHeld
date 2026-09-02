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
    photo_url: str | None = None
    photo_remove_white: bool = False

    def path(self, kind: str) -> Path:
        value = getattr(self, kind)
        return ASSET_ROOT / self.key / value


PLATFORM_ASSETS = {
    "vita": PlatformAssets(
        "playstation_vita", "PlayStation Vita", "device_large.svg", "device_small.svg", "logo.svg", "logo_dark.svg",
        "#111111", "#3b9cf5", True,
        "https://commons.wikimedia.org/wiki/File:PlayStation-Vita-1101-FL.png",
        "Original RommHeld vector retained as the offline fallback. The selector prefers the public-domain Evan-Amos PCH-1000 photograph below when available.",
        "https://commons.wikimedia.org/wiki/Special:Redirect/file/PlayStation-Vita-1101-FL.png",
        True,
    ),
    "3ds": PlatformAssets(
        "nintendo_3ds", "Nintendo 3DS", "device_large.svg", "device_small.svg", "logo.svg", "logo_dark.svg",
        "#25a6c9", "#d12228", True,
        "https://commons.wikimedia.org/wiki/File:Nintendo-3DS-AquaOpen.png",
        "Original RommHeld vector retained as the offline fallback. The selector prefers the public-domain Evan-Amos Aqua Blue photograph below when available.",
        "https://commons.wikimedia.org/wiki/Special:Redirect/file/Nintendo-3DS-AquaOpen.png",
        False,
    ),
    "ds": PlatformAssets(
        "nintendo_ds", "Nintendo DS", "device_large.svg", "device_small.svg", "logo.svg", "logo_dark.svg",
        "#dfe3e8", "#4b83b5", True,
        "https://commons.wikimedia.org/wiki/File:Nintendo-DS-Fat-Blue.png",
        "Original RommHeld vector retained as the offline fallback. The selector prefers the public-domain Evan-Amos blue Nintendo DS photograph below when available.",
        "https://commons.wikimedia.org/wiki/Special:Redirect/file/Nintendo-DS-Fat-Blue.png",
        False,
    ),
    "psp": PlatformAssets(
        "playstation_portable", "PlayStation Portable", "device_large.svg", "device_small.svg", "logo.svg", "logo_dark.svg",
        "#111111", "#777b84", True,
        "https://commons.wikimedia.org/wiki/File:Sony-PSP-1000-Body.png",
        "Original RommHeld vector retained as the offline fallback. The selector prefers the public-domain Evan-Amos PSP-1000 photograph below when available.",
        "https://commons.wikimedia.org/wiki/Special:Redirect/file/Sony-PSP-1000-Body.png",
        False,
    ),
}


def get_platform_assets(key: str) -> PlatformAssets | None:
    return PLATFORM_ASSETS.get(key)
