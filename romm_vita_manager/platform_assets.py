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
    logo_simpleicons: str | None = None
    logo_simpleicons_dark: str | None = None

    def path(self, kind: str) -> Path:
        value = getattr(self, kind)
        if value is None:
            raise ValueError(f"Asset '{kind}' is not defined for platform '{self.key}'")
        return ASSET_ROOT / self.key / value


PLATFORM_ASSETS = {
    "vita": PlatformAssets(
        "playstation_vita", "PlayStation Vita", "device_large.svg", "device_small.svg", "logo.svg", "logo_dark.svg",
        "#111111", "#3b9cf5", True,
        "https://commons.wikimedia.org/wiki/File:PlayStation_Vita_logo.svg",
        "Logo source reviewed on Wikimedia Commons; page identifies the image as public domain for copyright purposes and separately notes trademark restrictions.",
    ),
    "3ds": PlatformAssets(
        "nintendo_3ds", "Nintendo 3DS", "device_large.svg", "device_small.svg", "logo_simpleicons.svg", "logo_simpleicons_dark.svg",
        "#25a6c9", "#d12228", True,
        "https://www.nintendo.de/",
        "Platform mark uses the Nintendo 3DS Simple Icons rendering, whose source metadata points to Nintendo branding. Nintendo 3DS is a trademark of Nintendo; use remains subject to applicable trademark rules.",
        "logo_simpleicons.svg", "logo_simpleicons_dark.svg",
    ),
    "ds": PlatformAssets(
        "nintendo_ds", "Nintendo DS", "device_large.svg", "device_small.svg", "logo.svg", "logo_dark.svg",
        "#dfe3e8", "#4b83b5", True,
        "https://commons.wikimedia.org/wiki/File:Nintendo_DS_Logo.svg",
        "Logo source reviewed on Wikimedia Commons; source is a Nintendo DS manual and the page identifies the text logo as public domain for copyright purposes while separately noting trademark restrictions.",
    ),
}


def get_platform_assets(key: str) -> PlatformAssets | None:
    return PLATFORM_ASSETS.get(key)
