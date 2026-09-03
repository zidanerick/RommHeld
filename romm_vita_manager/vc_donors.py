from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import save_config


@dataclass(frozen=True)
class VcDonorFamily:
    key: str
    label: str
    platform_slugs: tuple[str, ...]
    requires_new_3ds: bool = False
    requires_boot9: bool = True
    requires_boot_logo: bool = False
    injector_key: str | None = None


VC_DONOR_FAMILIES: tuple[VcDonorFamily, ...] = (
    VcDonorFamily("gb", "Game Boy", ("gb",), injector_key=None),
    VcDonorFamily("gbc", "Game Boy Color", ("gbc",), injector_key=None),
    VcDonorFamily("gba", "Game Boy Advance", ("gba",), requires_boot_logo=True, injector_key="agbcia"),
    VcDonorFamily("nes", "NES", ("nes", "famicom", "fds"), injector_key=None),
    VcDonorFamily("snes", "Super Nintendo", ("snes",), requires_new_3ds=True, injector_key=None),
    VcDonorFamily("gamegear", "Game Gear", ("gamegear",), injector_key=None),
)

_FAMILY_BY_KEY = {family.key: family for family in VC_DONOR_FAMILIES}
_FAMILY_BY_PLATFORM = {
    slug: family
    for family in VC_DONOR_FAMILIES
    for slug in family.platform_slugs
}


def donor_family(key: str) -> VcDonorFamily:
    try:
        return _FAMILY_BY_KEY[key.lower()]
    except KeyError as exc:
        raise ValueError(f"Unknown Virtual Console donor family: {key}") from exc


def donor_family_for_platform(platform_slug: str) -> VcDonorFamily | None:
    return _FAMILY_BY_PLATFORM.get(platform_slug.lower())


def configured_donor_path(config: dict, family_key: str) -> Path | None:
    family = donor_family(family_key)
    settings = config.get("three_ds_vc", {})
    if not isinstance(settings, dict):
        return None
    donors = settings.get("donors", {})
    if not isinstance(donors, dict):
        return None
    value = donors.get(family.key)
    if not isinstance(value, dict):
        return None
    raw = str(value.get("cia_path", "")).strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.is_file() else None


def configure_donor(config: dict, family_key: str, cia_path: str | Path) -> dict:
    family = donor_family(family_key)
    path = Path(cia_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Virtual Console donor CIA does not exist: {path}")
    if path.suffix.lower() != ".cia":
        raise ValueError("Virtual Console donor must be a .cia file.")

    updated = dict(config)
    vc = dict(updated.get("three_ds_vc", {})) if isinstance(updated.get("three_ds_vc", {}), dict) else {}
    donors = dict(vc.get("donors", {})) if isinstance(vc.get("donors", {}), dict) else {}
    entry = dict(donors.get(family.key, {})) if isinstance(donors.get(family.key, {}), dict) else {}
    entry["cia_path"] = str(path)
    donors[family.key] = entry
    vc["donors"] = donors
    updated["three_ds_vc"] = vc
    save_config(updated)
    return updated


def configured_boot9_path(config: dict) -> Path | None:
    settings = config.get("three_ds_vc", {})
    if not isinstance(settings, dict):
        return None
    raw = str(settings.get("boot9_path", "")).strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.is_file() else None


def configure_boot9(config: dict, boot9_path: str | Path) -> dict:
    path = Path(boot9_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"boot9 dump does not exist: {path}")

    updated = dict(config)
    vc = dict(updated.get("three_ds_vc", {})) if isinstance(updated.get("three_ds_vc", {}), dict) else {}
    vc["boot9_path"] = str(path)
    updated["three_ds_vc"] = vc
    save_config(updated)
    return updated


def donor_readiness(config: dict, platform_slug: str) -> tuple[bool, str]:
    family = donor_family_for_platform(platform_slug)
    if family is None:
        return False, "Nintendo did not provide a supported 3DS Virtual Console family for this platform."
    donor = configured_donor_path(config, family.key)
    if donor is None:
        return False, f"Configure a {family.label} Virtual Console donor CIA first."
    if family.requires_boot9 and configured_boot9_path(config) is None:
        return False, "Configure a valid boot9.bin/boot9_prot.bin dump first."
    if family.injector_key is None:
        return False, f"{family.label} donor is configured, but its family-specific injector is not implemented yet."
    return True, f"{family.label} donor assets are configured."
