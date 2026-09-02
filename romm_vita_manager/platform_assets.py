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
        value = getattr(self, kind)
        return ASSET_ROOT / self.key / value


PLATFORM_ASSETS = {
    "vita": PlatformAssets(
        "playstation_vita", "PlayStation Vita", "device_large.svg", "device_small.svg", "logo.svg", "logo_dark.svg",
        "#111111", "#3b9cf5", True,
        "https://icons8.com/icon/13629/playstation",
        "Original RommHeld handheld artwork visually inspired by the user's selected Icons8 Color reference. No Icons8 asset is bundled.",
    ),
    "3ds": PlatformAssets(
        "nintendo_3ds", "Nintendo 3DS", "device_large.svg", "device_small.svg", "logo_simpleicons.svg", "logo_simpleicons_dark.svg",
        "#25a6c9", "#d12228", True,
        "https://icons8.com/icon/fdVLfvnTjw0H/3ds-console",
        "Original RommHeld handheld artwork visually inspired by the user's selected Icons8 Color reference. Platform logo remains separately sourced.",
    ),
    "ds": PlatformAssets(
        "nintendo_ds", "Nintendo DS", "device_large.svg", "device_small.svg", "logo.svg", "logo_dark.svg",
        "#dfe3e8", "#4b83b5", True,
        "https://icons8.com/icon/19599/nintendo-ds",
        "Original RommHeld handheld artwork visually inspired by the user's selected Icons8 Color reference. Platform logo remains separately sourced.",
    ),
    "psp": PlatformAssets(
        "playstation_portable", "PlayStation Portable", "device_large.svg", "device_small.svg", "logo.svg", "logo_dark.svg",
        "#111111", "#777b84", True,
        "https://icons8.com/icon/xv4xoRkYlmXq/playstation-portable",
        "Original RommHeld handheld artwork visually inspired by the user's selected Icons8 Color reference. PSP remains a coming-soon target.",
    ),
}


def get_platform_assets(key: str) -> PlatformAssets | None:
    return PLATFORM_ASSETS.get(key)
