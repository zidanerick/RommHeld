from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeploymentTarget:
    key: str
    label: str
    description: str
    destination_kind: str


NATIVE_GBA = DeploymentTarget(
    "native_gba",
    "Nintendo GBA (AGB_FIRM)",
    "Native 3DS GBA runtime. Requires the user's extracted AGB_FIRM donor assets.",
    "native",
)

VC_CIA = DeploymentTarget(
    "vc_cia",
    "Virtual Console-style CIA",
    "Create an installable CIA with per-title Home Menu metadata and artwork.",
    "cia",
)

NATIVE_3DS_CIA = DeploymentTarget(
    "native_3ds_cia",
    "Nintendo 3DS CIA",
    "Transfer an existing 3DS application CIA without repackaging it.",
    "cia",
)

RETROARCH = DeploymentTarget(
    "retroarch",
    "RetroArch ROM",
    "Copy the original ROM into the configured 3DS RetroArch ROM tree.",
    "retroarch",
)

# Platforms for which the current Nintendo 3DS RetroArch build publishes
# usable core CIA packages. This is intentionally an explicit 3DS list rather
# than inheriting the Vita RetroFlow mapping.
RETROARCH_PLATFORM_SLUGS = frozenset(
    {
        "3ds",
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
        "amiga",
        "dos",
        "scummvm",
        "wonderswan",
        "wonderswan-color",
        "neogeomvs",
        "neo-geo-pocket",
        "neo-geo-pocket-color",
        "zxs",
        "turbografx-cd",
    }
)

VC_RESEARCH_PLATFORM_SLUGS = frozenset({"gb", "gbc", "gba", "nes", "snes", "gamegear"})
NATIVE_PLATFORM_SLUGS = frozenset({"gba"})


def compatible_platform(slug: str) -> bool:
    return slug.lower() in RETROARCH_PLATFORM_SLUGS


def available_targets(slug: str) -> tuple[DeploymentTarget, ...]:
    key = slug.lower()
    targets: list[DeploymentTarget] = []
    if key in NATIVE_PLATFORM_SLUGS:
        targets.append(NATIVE_GBA)
    if key == "3ds":
        targets.append(NATIVE_3DS_CIA)
    elif key in RETROARCH_PLATFORM_SLUGS:
        targets.append(RETROARCH)
    if key in VC_RESEARCH_PLATFORM_SLUGS:
        targets.append(VC_CIA)
    return tuple(targets)


def default_destination(target_key: str, platform_slug: str, filename: str) -> str:
    safe_name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    slug = platform_slug.lower()
    if target_key == "retroarch":
        return f"/RetroArch/roms/{slug}/{safe_name}"
    if target_key in {"native_gba", "native_3ds_cia", "vc_cia"}:
        return f"/cias/{safe_name.rsplit('.', 1)[0]}.cia"
    return safe_name
