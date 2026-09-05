from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class DeploymentTarget:
    key: str
    label: str
    description: str
    destination_kind: str


OPEN_AGB_FIRM = DeploymentTarget(
    "open_agb_firm",
    "open_agb_firm GBA ROM",
    "Copy the original GBA ROM to the SD card for direct launch through open_agb_firm. This is separate from creating an installable HOME Menu CIA.",
    "native_rom",
)

NATIVE_GBA = DeploymentTarget(
    "native_gba",
    "GBA HOME Menu CIA (AGB_FIRM)",
    "Create an installable GBA CIA that runs through the 3DS native AGB_FIRM runtime using the user's prepared donor assets.",
    "cia",
)

VC_CIA = DeploymentTarget(
    "vc_cia",
    "Nintendo Virtual Console CIA",
    "Create an installable Nintendo Virtual Console CIA using the family-specific runtime for this platform.",
    "cia",
)

NATIVE_3DS_CIA = DeploymentTarget(
    "native_3ds_cia",
    "Nintendo 3DS CIA",
    "Transfer an existing 3DS application CIA without repackaging it.",
    "cia",
)

TWILIGHT_NDS = DeploymentTarget(
    "twilight",
    "TWiLight Menu++ / nds-bootstrap",
    "Copy the Nintendo DS ROM to the conventional 3DS SD ROM tree for launch through TWiLight Menu++ and nds-bootstrap.",
    "native_rom",
)

RED_VIPER = DeploymentTarget(
    "red_viper",
    "Red Viper",
    "Copy the Virtual Boy ROM to the 3DS SD card for use with the dedicated Red Viper emulator.",
    "emulator",
)

DAEDALUSX64 = DeploymentTarget(
    "daedalusx64",
    "DaedalusX64",
    "Copy the Nintendo 64 ROM to DaedalusX64's documented 3DS ROM directory.",
    "emulator",
)

RETROARCH = DeploymentTarget(
    "retroarch",
    "RetroArch ROM",
    "Copy the original ROM into the shared 3DS ROM tree for use with the selected RetroArch core. RetroArch content does not need to live inside /RetroArch.",
    "retroarch",
)

# Platforms for which the current official 3DS RetroArch recipe builds a
# usable core route that RommHeld intentionally exposes. Dedicated runtimes are
# tracked separately below. N64 is intentionally absent: the current 3DS
# recipe does not build a Mupen64Plus/ParaLLEl N64 core. Amiga and ScummVM are
# also absent from that recipe and must not be advertised as RetroArch routes.
RETROARCH_TARGET_PLATFORM_SLUGS = frozenset(
    {
        "gba",
        "gb",
        "gbc",
        "nes",
        "famicom",
        "fds",
        "snes",
        "gamegear",
        "sms",
        "genesis",
        "sega32",
        "segacd",
        "msx",
        "msx2",
        "atari5200",
        "atari7800",
        "lynx",
        "vectrex",
        "colecovision",
        "c64",
        "dos",
        "wonderswan",
        "wonderswan-color",
        "neogeomvs",
        "neo-geo-pocket",
        "neo-geo-pocket-color",
        "zxs",
        "turbografx-cd",
    }
)

# Conservative current 3DS RetroArch routes where the official 3DS core bundle
# contains a core that Libretro currently documents with memory-monitoring
# support suitable for achievement integration. Keep this narrower than the
# general RetroArch platform set when capability is not independently verified.
RETROACHIEVEMENTS_RETROARCH_PLATFORM_SLUGS = frozenset(
    {
        "gba",        # mGBA
        "gb",         # Gambatte / mGBA
        "gbc",        # Gambatte / mGBA
        "nes",        # FCEUmm / QuickNES
        "famicom",    # FCEUmm
        "fds",        # FCEUmm
        "gamegear",   # Genesis Plus GX
        "sms",        # Genesis Plus GX / PicoDrive / SMS Plus GX
        "genesis",    # Genesis Plus GX / PicoDrive / ClownMDEmu
        "sega32",     # PicoDrive
        "segacd",     # Genesis Plus GX / PicoDrive
    }
)

DIRECT_RUNTIME_PLATFORM_SLUGS = frozenset({"3ds", "gba", "nds", "virtualboy", "n64"})
THREE_DS_PLATFORM_SLUGS = RETROARCH_TARGET_PLATFORM_SLUGS | DIRECT_RUNTIME_PLATFORM_SLUGS

# Compatibility alias. Existing RomM library code historically used this name
# as the general set of platforms visible in the 3DS workspace, even though the
# name implied RetroArch. Keep that code working while target selection itself
# uses RETROARCH_TARGET_PLATFORM_SLUGS and therefore does not invent a
# RetroArch route for dedicated-only platforms such as NDS, Virtual Boy, or N64.
RETROARCH_PLATFORM_SLUGS = THREE_DS_PLATFORM_SLUGS

# Every slug listed here has a concrete family-specific package builder and
# PC-side structural validation. Hardware validation status is tracked
# separately; exposure never means another family is routed through GBA code.
VC_IMPLEMENTED_PLATFORM_SLUGS = frozenset(
    {"gba", "gb", "gbc", "nes", "gamegear", "snes"}
)
NATIVE_PLATFORM_SLUGS = frozenset({"gba"})

# These are target-selection defaults, not claims that every title works best
# with one runtime. They keep the common dedicated/native path distinct from an
# explicit RetroAchievements preference while still allowing the user to choose
# another exposed target per title.
DEDICATED_COMPATIBILITY_TARGETS = {
    "gba": "open_agb_firm",
    "nds": "twilight",
    "virtualboy": "red_viper",
    "n64": "daedalusx64",
    "3ds": "native_3ds_cia",
}


def compatible_platform(slug: str) -> bool:
    return slug.lower() in THREE_DS_PLATFORM_SLUGS


def available_targets(slug: str) -> tuple[DeploymentTarget, ...]:
    key = slug.lower()
    targets: list[DeploymentTarget] = []

    if key == "gba":
        targets.extend((OPEN_AGB_FIRM, NATIVE_GBA))
    elif key == "nds":
        targets.append(TWILIGHT_NDS)
    elif key == "virtualboy":
        targets.append(RED_VIPER)
    elif key == "n64":
        targets.append(DAEDALUSX64)

    if key == "3ds":
        targets.append(NATIVE_3DS_CIA)
    elif key in RETROARCH_TARGET_PLATFORM_SLUGS:
        targets.append(RETROARCH)

    if key in VC_IMPLEMENTED_PLATFORM_SLUGS:
        targets.append(VC_CIA)
    return tuple(targets)


def _payload_suffix(filename: str) -> str:
    normalized = str(filename or "").replace("\\", "/")
    return PurePosixPath(normalized).suffix.casefold()


def available_targets_for_file(
    slug: str,
    filename: str,
) -> tuple[DeploymentTarget, ...]:
    """Return only targets that can consume the existing payload as supplied."""
    targets = available_targets(slug)
    if slug.lower() == "3ds" and _payload_suffix(filename) != ".cia":
        return tuple(target for target in targets if target.key != "native_3ds_cia")
    return targets


def preferred_target_key(slug: str, preference: str = "compatibility") -> str | None:
    """Return a preferred target without inventing unsupported runtime routes."""
    key = slug.lower()
    targets = available_targets(key)
    if not targets:
        return None
    target_keys = {target.key for target in targets}

    if preference == "retroachievements":
        if (
            key in RETROACHIEVEMENTS_RETROARCH_PLATFORM_SLUGS
            and "retroarch" in target_keys
        ):
            return "retroarch"
        dedicated = DEDICATED_COMPATIBILITY_TARGETS.get(key)
        if dedicated in target_keys:
            return dedicated
        if "vc_cia" in target_keys:
            return "vc_cia"

    if preference == "native":
        dedicated = DEDICATED_COMPATIBILITY_TARGETS.get(key)
        if dedicated in target_keys:
            return dedicated
        if "vc_cia" in target_keys:
            return "vc_cia"

    dedicated = DEDICATED_COMPATIBILITY_TARGETS.get(key)
    if dedicated in target_keys:
        return dedicated
    if "retroarch" in target_keys:
        return "retroarch"
    return targets[0].key


def default_destination(target_key: str, platform_slug: str, filename: str) -> str:
    safe_name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    slug = platform_slug.lower()
    if target_key == "open_agb_firm":
        return f"/roms/gba/{safe_name}"
    if target_key == "twilight":
        return f"/roms/nds/{safe_name}"
    if target_key == "red_viper":
        return f"/roms/virtualboy/{safe_name}"
    if target_key == "daedalusx64":
        return f"/3ds/DaedalusX64/Roms/{safe_name}"
    if target_key == "retroarch":
        return f"/roms/{slug}/{safe_name}"
    if target_key == "native_3ds_cia":
        if _payload_suffix(safe_name) != ".cia":
            raise ValueError(
                "The existing Nintendo 3DS package route requires a .cia source file; "
                f"refusing to rename {safe_name!r} into an installable CIA destination."
            )
        return f"/cias/{safe_name}"
    if target_key in {"native_gba", "vc_cia"}:
        return f"/cias/{safe_name.rsplit('.', 1)[0]}.cia"
    return safe_name
