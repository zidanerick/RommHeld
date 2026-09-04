from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VirtualConsoleProfile:
    key: str
    label: str
    platform_slugs: tuple[str, ...]
    source_extensions: tuple[str, ...]
    output_extension: str
    runtime: str
    requires_boot_logo: bool = False
    requires_boot9: bool = False
    requires_new_3ds: bool = False
    title_id_pattern: str | None = None
    implemented: bool = False


GB_PROFILE = VirtualConsoleProfile(
    key="gb",
    label="Game Boy Virtual Console",
    platform_slugs=("gb",),
    source_extensions=(".gb",),
    output_extension=".cia",
    runtime="nintendo-gb-vc",
    requires_boot9=True,
    implemented=True,
)

GBC_PROFILE = VirtualConsoleProfile(
    key="gbc",
    label="Game Boy Color Virtual Console",
    platform_slugs=("gbc",),
    source_extensions=(".gbc", ".gb"),
    output_extension=".cia",
    runtime="nintendo-gbc-vc",
    requires_boot9=True,
    implemented=True,
)

GBA_NATIVE_PROFILE = VirtualConsoleProfile(
    key="gba",
    label="Game Boy Advance Virtual Console (AGB_FIRM)",
    platform_slugs=("gba",),
    source_extensions=(".gba", ".agb"),
    output_extension=".cia",
    runtime="nintendo-agb-firm",
    requires_boot_logo=True,
    requires_boot9=True,
    title_id_pattern="0004000000F???00",
    implemented=True,
)

NES_PROFILE = VirtualConsoleProfile(
    key="nes",
    label="NES Virtual Console",
    # The native TNES builder currently accepts cartridge iNES/NES2 ROMs.
    # Famicom/FDS remain available through RetroArch until disk-system payload
    # generation is independently implemented.
    platform_slugs=("nes",),
    source_extensions=(".nes",),
    output_extension=".cia",
    runtime="nintendo-nes-vc",
    requires_boot9=True,
    implemented=True,
)

SNES_PROFILE = VirtualConsoleProfile(
    key="snes",
    label="Super Nintendo Virtual Console",
    platform_slugs=("snes",),
    source_extensions=(".sfc", ".smc"),
    output_extension=".cia",
    runtime="nintendo-snes-vc",
    requires_boot9=True,
    requires_new_3ds=True,
)

GAME_GEAR_PROFILE = VirtualConsoleProfile(
    key="gamegear",
    label="Game Gear Virtual Console",
    platform_slugs=("gamegear",),
    source_extensions=(".gg",),
    output_extension=".cia",
    runtime="nintendo-gamegear-vc",
    requires_boot9=True,
)


PROFILES = (
    GB_PROFILE,
    GBC_PROFILE,
    GBA_NATIVE_PROFILE,
    NES_PROFILE,
    SNES_PROFILE,
    GAME_GEAR_PROFILE,
)

_PROFILE_BY_PLATFORM = {
    slug: profile
    for profile in PROFILES
    for slug in profile.platform_slugs
}


def profile_for_platform(platform_slug: str) -> VirtualConsoleProfile | None:
    return _PROFILE_BY_PLATFORM.get(platform_slug.lower())


def profile_for_rom(path: str | Path) -> VirtualConsoleProfile | None:
    suffix = Path(path).suffix.lower()
    return next((profile for profile in PROFILES if suffix in profile.source_extensions), None)


def validate_native_gba_title_id(title_id: str) -> str:
    value = title_id.strip().lower()
    if len(value) != 16:
        raise ValueError("GBA native Virtual Console title IDs must contain 16 hexadecimal digits.")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError("GBA native Virtual Console title IDs must contain only hexadecimal digits.") from exc
    if not (value.startswith("0004000000f") and value.endswith("00")):
        raise ValueError("GBA native Virtual Console title IDs must match 0004000000F???00.")
    return value


def validate_gba_native_assets(*, boot_logo: str | Path | None, boot9: str | Path | None) -> None:
    for label, value in (("AGB_FIRM boot logo", boot_logo), ("boot9 dump", boot9)):
        if value is None or not Path(value).expanduser().is_file():
            raise FileNotFoundError(f"A valid {label} file is required for native GBA packaging.")
