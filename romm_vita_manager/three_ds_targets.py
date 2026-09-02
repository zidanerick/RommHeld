from __future__ import annotations

from dataclasses import dataclass

from .mappings import ROMM_TO_RETROFLOW


@dataclass(frozen=True)
class DeploymentTarget:
    key: str
    label: str
    description: str
    destination_kind: str


NATIVE_GBA = DeploymentTarget(
    "native_gba",
    "Nintendo GBA (AGB_FIRM)",
    "Native 3DS GBA runtime. Requires the user's extracted AGB_FIRM assets.",
    "native",
)

VC_CIA = DeploymentTarget(
    "vc_cia",
    "Virtual Console-style CIA",
    "Pack the ROM into an installable CIA with generated Home Menu metadata.",
    "cia",
)

RETROARCH = DeploymentTarget(
    "retroarch",
    "RetroArch ROM",
    "Copy the original ROM into RommHeld's managed RetroArch ROM tree.",
    "retroarch",
)

# Platforms with a known RetroArch-oriented mapping already maintained by
# RommHeld. Native/VC capabilities are layered on top of this set separately.
RETROARCH_PLATFORM_SLUGS = frozenset(ROMM_TO_RETROFLOW) | {
    "gamegear",
    "gba",
    "gb",
    "gbc",
    "nes",
    "snes",
}

# Nintendo released Virtual Console-style titles for these 3DS-era classic
# platforms. Packaging support is deliberately separate from whether an
# official Nintendo title exists for a particular ROM.
VC_RESEARCH_PLATFORM_SLUGS = frozenset({"gb", "gbc", "gba", "nes", "snes", "gamegear"})

# Native AGB_FIRM packaging is currently implemented only for GBA.
NATIVE_PLATFORM_SLUGS = frozenset({"gba"})


def compatible_platform(slug: str) -> bool:
    return slug.lower() in RETROARCH_PLATFORM_SLUGS


def available_targets(slug: str) -> tuple[DeploymentTarget, ...]:
    key = slug.lower()
    targets: list[DeploymentTarget] = []
    if key in NATIVE_PLATFORM_SLUGS:
        targets.append(NATIVE_GBA)
    if key in RETROARCH_PLATFORM_SLUGS:
        targets.append(RETROARCH)
    if key in VC_RESEARCH_PLATFORM_SLUGS:
        targets.append(VC_CIA)
    return tuple(targets)


def default_destination(target_key: str, platform_slug: str, filename: str) -> str:
    slug = platform_slug.lower()
    safe_name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if target_key == "retroarch":
        return f"/RetroArch/roms/{slug}/{safe_name}"
    if target_key == "native_gba":
        return f"/roms/gba/{safe_name}"
    if target_key == "vc_cia":
        return f"/cias/{safe_name.rsplit('.', 1)[0]}.cia"
    return safe_name
