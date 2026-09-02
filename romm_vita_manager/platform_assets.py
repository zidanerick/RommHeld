from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parent.parent / "assets" / "handhelds"
ICONS8_ROOT = ASSET_ROOT / "icons8"


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
    logo_role: str = "wordmark"
    icons8_icon: str | None = None
    icons8_source: str | None = None

    def path(self, kind: str) -> Path:
        value = getattr(self, kind)
        if value is None:
            raise ValueError(f"Asset '{kind}' is not defined for platform '{self.key}'")
        if kind == "icons8_icon":
            return ICONS8_ROOT / value
        return ASSET_ROOT / self.key / value


PLATFORM_ASSETS = {
    "vita": PlatformAssets(
        "playstation_vita", "PlayStation Vita", "device_large.svg", "device_small.svg", "logo.svg", "logo_dark.svg",
        "#111111", "#3b9cf5", True,
        "https://icons8.com/icon/13629/playstation",
        "Icons8 Color PlayStation icon used as a visual handheld-family identifier. Free use requires an Icons8 attribution link in the application.",
        logo_role="wordmark",
        icons8_icon="vita.png",
        icons8_source="https://icons8.com/icon/13629/playstation",
    ),
    "3ds": PlatformAssets(
        "nintendo_3ds", "Nintendo 3DS", "device_large.svg", "device_small.svg", "logo_simpleicons.svg", "logo_simpleicons_dark.svg",
        "#25a6c9", "#d12228", True,
        "https://icons8.com/icon/fdVLfvnTjw0H/3ds-console",
        "Icons8 Color 3DS Console icon. Free use requires an Icons8 attribution link in the application.",
        logo_simpleicons="logo_simpleicons.svg", logo_simpleicons_dark="logo_simpleicons_dark.svg", logo_role="icon",
        icons8_icon="3ds.png",
        icons8_source="https://icons8.com/icon/fdVLfvnTjw0H/3ds-console",
    ),
    "ds": PlatformAssets(
        "nintendo_ds", "Nintendo DS", "device_large.svg", "device_small.svg", "logo.svg", "logo_dark.svg",
        "#dfe3e8", "#4b83b5", True,
        "https://icons8.com/icon/19599/nintendo-ds",
        "Icons8 Color Nintendo DS icon. Free use requires an Icons8 attribution link in the application.",
        logo_simpleicons="logo.svg", logo_simpleicons_dark="logo_dark.svg", logo_role="wordmark",
        icons8_icon="ds.png",
        icons8_source="https://icons8.com/icon/19599/nintendo-ds",
    ),
    "psp": PlatformAssets(
        "playstation_portable", "PlayStation Portable", "device_large.svg", "device_small.svg", "logo.svg", "logo_dark.svg",
        "#111111", "#777b84", True,
        "https://icons8.com/icon/xv4xoRkYlmXq/playstation-portable",
        "Icons8 Color PlayStation Portable icon. Free use requires an Icons8 attribution link in the application.",
        icons8_icon="psp.png",
        icons8_source="https://icons8.com/icon/xv4xoRkYlmXq/playstation-portable",
    ),
}


def get_platform_assets(key: str) -> PlatformAssets | None:
    return PLATFORM_ASSETS.get(key)
