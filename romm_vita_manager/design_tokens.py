from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    background: str
    sidebar: str
    surface: str
    surface_raised: str
    surface_hover: str
    separator: str
    text_primary: str
    text_secondary: str
    text_tertiary: str
    success: str
    warning: str
    error: str


@dataclass(frozen=True)
class PlatformBrand:
    key: str
    name: str
    accent: str
    accent_hover: str
    accent_soft: str


# Neutral dark surfaces intentionally resemble modern desktop system UI rather
# than any specific proprietary interface.
DARK = Palette(
    background="#0B0B0D",
    sidebar="#141416",
    surface="#1C1C1E",
    surface_raised="#242426",
    surface_hover="#2C2C2E",
    separator="#38383A",
    text_primary="#F5F5F7",
    text_secondary="#A1A1A6",
    text_tertiary="#727277",
    success="#30D158",
    warning="#FF9F0A",
    error="#FF453A",
)


# Manufacturer-family accents. These are orientation accents only: the app
# stays neutral and uses the brand colour sparingly for selection and primary
# actions.
BRANDS: dict[str, PlatformBrand] = {
    "nintendo": PlatformBrand("nintendo", "Nintendo", "#E60012", "#FF1A2B", "#351014"),
    "sony": PlatformBrand("sony", "Sony / PlayStation", "#0070D1", "#1687E5", "#0C2740"),
    "xbox": PlatformBrand("xbox", "Xbox", "#107C10", "#159615", "#153415"),
    "sega": PlatformBrand("sega", "Sega", "#0089CF", "#10A0E8", "#0C2D3D"),
    "neutral": PlatformBrand("neutral", "Neutral", "#6E6E73", "#85858B", "#2A2A2D"),
}


PLATFORM_FAMILIES: dict[str, str] = {
    "vita": "sony",
    "psvita": "sony",
    "psp": "sony",
    "playstation_portable": "sony",
    "3ds": "nintendo",
    "nintendo_3ds": "nintendo",
    "ds": "nintendo",
    "nintendo_ds": "nintendo",
    "gba": "nintendo",
    "game_boy_advance": "nintendo",
    "gb": "nintendo",
    "gbc": "nintendo",
    "switch": "nintendo",
    "xbox": "xbox",
    "xbox360": "xbox",
    "xbox_one": "xbox",
    "dreamcast": "sega",
    "saturn": "sega",
    "genesis": "sega",
    "megadrive": "sega",
}


# Shared geometry. Keeping these values here prevents every widget from
# inventing its own margins and corner radii.
SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_5 = 20
SPACE_6 = 24
SPACE_8 = 32

RADIUS_SMALL = 8
RADIUS_MEDIUM = 12
RADIUS_LARGE = 16

SIDEBAR_WIDTH = 238
CONTENT_MAX_WIDTH = 1440


def brand_for_platform(platform_key: str | None) -> PlatformBrand:
    key = (platform_key or "").strip().lower()
    family = PLATFORM_FAMILIES.get(key, "neutral")
    return BRANDS[family]


__all__ = [
    "BRANDS",
    "CONTENT_MAX_WIDTH",
    "DARK",
    "PLATFORM_FAMILIES",
    "Palette",
    "PlatformBrand",
    "RADIUS_LARGE",
    "RADIUS_MEDIUM",
    "RADIUS_SMALL",
    "SIDEBAR_WIDTH",
    "SPACE_1",
    "SPACE_2",
    "SPACE_3",
    "SPACE_4",
    "SPACE_5",
    "SPACE_6",
    "SPACE_8",
    "brand_for_platform",
]
