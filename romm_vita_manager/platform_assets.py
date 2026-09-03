from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .design_tokens import brand_for_platform

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
    logo_role: str = "wordmark"
    logo_simpleicons: str | None = None
    logo_simpleicons_dark: str | None = None

    def path(self, kind: str) -> Path:
        value = getattr(self, kind)
        if not value:
            raise ValueError(f"Asset {kind!r} is not defined for {self.name}.")
        return ASSET_ROOT / self.key / value


PLATFORM_ASSETS = {
    "vita": PlatformAssets(
        "playstation_vita",
        "PlayStation Vita",
        "device_large.svg",
        "device_small.svg",
        "logo.svg",
        "logo_dark.svg",
        "#111111",
        brand_for_platform("vita").accent,
        True,
        "https://commons.wikimedia.org/wiki/File:PlayStation-Vita-1101-FL.png",
        "Original RommHeld vector retained as the offline fallback. The selector prefers the public-domain Evan-Amos PCH-1000 photograph below when available.",
        "https://commons.wikimedia.org/wiki/Special:Redirect/file/PlayStation-Vita-1101-FL.png",
        True,
        "wordmark",
    ),
    "3ds": PlatformAssets(
        "nintendo_3ds",
        "Nintendo 3DS",
        "device_large.svg",
        "device_small.svg",
        "logo_simpleicons.svg",
        "logo_simpleicons_dark.svg",
        "#25a6c9",
        brand_for_platform("3ds").accent,
        True,
        "https://commons.wikimedia.org/wiki/File:Nintendo-3DS-AquaOpen.png",
        "Original RommHeld vector retained as the offline fallback. The selector prefers the public-domain Evan-Amos Aqua Blue photograph below when available.",
        "https://commons.wikimedia.org/wiki/Special:Redirect/file/Nintendo-3DS-AquaOpen.png",
        False,
        "icon",
        "logo_simpleicons.svg",
        "logo_simpleicons_dark.svg",
    ),
    "ds": PlatformAssets(
        "nintendo_ds",
        "Nintendo DS",
        "device_large.svg",
        "device_small.svg",
        "logo.svg",
        "logo_dark.svg",
        "#dfe3e8",
        brand_for_platform("ds").accent,
        True,
        "https://commons.wikimedia.org/wiki/File:Nintendo-DS-Fat-Blue.png",
        "Original RommHeld vector retained as the offline fallback. The selector prefers the public-domain Evan-Amos blue Nintendo DS photograph below when available.",
        "https://commons.wikimedia.org/wiki/Special:Redirect/file/Nintendo-DS-Fat-Blue.png",
        False,
        "wordmark",
    ),
    "psp": PlatformAssets(
        "playstation_portable",
        "PlayStation Portable",
        "device_large.svg",
        "device_small.svg",
        "logo.svg",
        "logo_dark.svg",
        "#111111",
        brand_for_platform("psp").accent,
        True,
        "https://commons.wikimedia.org/wiki/File:Sony-PSP-1000-Body.png",
        "Original RommHeld vector retained as the offline fallback. The selector prefers the public-domain Evan-Amos PSP-1000 photograph below when available.",
        "https://commons.wikimedia.org/wiki/Special:Redirect/file/Sony-PSP-1000-Body.png",
        False,
        "wordmark",
    ),
}


def get_platform_assets(key: str) -> PlatformAssets | None:
    return PLATFORM_ASSETS.get(key)
