from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .config import save_config


_FULL_BOOT9_SIZE = 0x10000
_PROT_BOOT9_SIZE = 0x8000
_FULL_BOOT9_SHA256 = "2f88744feed717856386400a44bba4b9ca62e76a32c715d4f309c399bf28166f"
_PROT_BOOT9_SHA256 = "7331f7edece3dd33f2ab4bd0b3a5d607229fd19212c10b734cedcaf78c1a7b98"
_CIA_HEADER_SIZE = 0x2020


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
    VcDonorFamily("gb", "Game Boy", ("gb",), injector_key="classic_vc"),
    VcDonorFamily("gbc", "Game Boy Color", ("gbc",), injector_key="classic_vc"),
    VcDonorFamily("gba", "Game Boy Advance", ("gba",), requires_boot_logo=True, injector_key="agbcia"),
    # The TNES builder currently accepts cartridge iNES/NES2 inputs only.
    # Famicom/FDS remain explicit RetroArch routes rather than being silently
    # associated with a donor format that has not been verified for them.
    VcDonorFamily("nes", "NES", ("nes",), injector_key="classic_vc"),
    VcDonorFamily(
        "snes",
        "Super Nintendo",
        ("snes",),
        requires_new_3ds=True,
        injector_key="classic_vc",
    ),
    VcDonorFamily("gamegear", "Game Gear", ("gamegear",), injector_key="classic_vc"),
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


def validate_boot9(path: str | Path) -> str:
    candidate = Path(path).expanduser()
    if not candidate.is_file():
        raise FileNotFoundError(f"boot9 dump does not exist: {candidate}")
    data = candidate.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) == _FULL_BOOT9_SIZE and digest == _FULL_BOOT9_SHA256:
        return "full"
    if len(data) == _PROT_BOOT9_SIZE and digest == _PROT_BOOT9_SHA256:
        return "protected"
    raise ValueError(
        "boot9 dump does not match the known retail boot9.bin or boot9_prot.bin hash."
    )


def inspect_cia_container(path: str | Path) -> tuple[str, int]:
    """Return (ticket title ID, content count) after conservative CIA checks.

    This intentionally validates only the outer CIA structure. Family-specific
    NCCH/runtime validation happens in the injector because encrypted donor
    content can require boot9 and, for New 3DS SNES titles, public seed data.
    """
    candidate = Path(path).expanduser()
    if not candidate.is_file():
        raise FileNotFoundError(f"Virtual Console donor CIA does not exist: {candidate}")
    data = candidate.read_bytes()
    if len(data) < _CIA_HEADER_SIZE:
        raise ValueError("Virtual Console donor is too small to be a valid CIA.")
    header_size = int.from_bytes(data[0:4], "little")
    if header_size != _CIA_HEADER_SIZE:
        raise ValueError(f"Unexpected CIA header size: {header_size:#x}")
    cert_size = int.from_bytes(data[0x08:0x0C], "little")
    ticket_size = int.from_bytes(data[0x0C:0x10], "little")
    tmd_size = int.from_bytes(data[0x10:0x14], "little")
    if not cert_size or ticket_size < 0x1E4 or not tmd_size:
        raise ValueError("CIA is missing required certificate, ticket, or TMD data.")

    align64 = lambda value: (value + 63) & ~63
    ticket_offset = align64(header_size) + align64(cert_size)
    tmd_offset = align64(ticket_offset + ticket_size)
    if tmd_offset + tmd_size > len(data):
        raise ValueError("CIA metadata extends past the end of the file.")

    ticket = data[ticket_offset : ticket_offset + ticket_size]
    title_id = ticket[0x1DC:0x1E4].hex()
    if len(title_id) != 16 or int(title_id, 16) == 0:
        raise ValueError("CIA ticket does not contain a usable title ID.")

    sig_type = int.from_bytes(data[tmd_offset : tmd_offset + 4], "big")
    signature_sizes = {
        0x00010000: 0x23C,
        0x00010001: 0x13C,
        0x00010002: 0x7C,
        0x00010003: 0x23C,
        0x00010004: 0x13C,
        0x00010005: 0x7C,
    }
    sig_size = signature_sizes.get(sig_type)
    if sig_size is None:
        raise ValueError(f"Unsupported CIA TMD signature type: {sig_type:#x}")
    tmd_header = tmd_offset + 4 + sig_size
    content_count = int.from_bytes(data[tmd_header + 0x9E : tmd_header + 0xA0], "big")
    if content_count < 1:
        raise ValueError("CIA TMD does not reference any content.")
    return title_id, content_count


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


def configured_donor_info(config: dict, family_key: str) -> dict:
    family = donor_family(family_key)
    settings = config.get("three_ds_vc", {})
    donors = settings.get("donors", {}) if isinstance(settings, dict) else {}
    value = donors.get(family.key, {}) if isinstance(donors, dict) else {}
    return dict(value) if isinstance(value, dict) else {}


def configure_donor(config: dict, family_key: str, cia_path: str | Path) -> dict:
    family = donor_family(family_key)
    path = Path(cia_path).expanduser()
    if path.suffix.lower() != ".cia":
        raise ValueError("Virtual Console donor must be a .cia file.")
    title_id, content_count = inspect_cia_container(path)

    updated = dict(config)
    vc = dict(updated.get("three_ds_vc", {})) if isinstance(updated.get("three_ds_vc", {}), dict) else {}
    donors = dict(vc.get("donors", {})) if isinstance(vc.get("donors", {}), dict) else {}
    entry = dict(donors.get(family.key, {})) if isinstance(donors.get(family.key, {}), dict) else {}
    entry["cia_path"] = str(path)
    entry["title_id"] = title_id
    entry["content_count"] = content_count
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
    if not path.is_file():
        return None
    try:
        validate_boot9(path)
    except (OSError, ValueError):
        return None
    return path


def configure_boot9(config: dict, boot9_path: str | Path) -> dict:
    path = Path(boot9_path).expanduser()
    variant = validate_boot9(path)

    updated = dict(config)
    vc = dict(updated.get("three_ds_vc", {})) if isinstance(updated.get("three_ds_vc", {}), dict) else {}
    vc["boot9_path"] = str(path)
    vc["boot9_variant"] = variant
    updated["three_ds_vc"] = vc
    save_config(updated)
    return updated


def _cached_classic_runtime_ready(config: dict, family_key: str) -> bool:
    # Keep readiness tied to the exact cache contract used by deployment. A
    # simple path-exists check previously let stale cache versions report
    # "ready" even though configured_classic_runtime() would reject them.
    try:
        from .classic_vc_assets import configured_classic_runtime

        return configured_classic_runtime(config, family_key) is not None
    except (OSError, ValueError):
        return False


def _cached_gba_runtime_ready(config: dict) -> bool:
    settings = config.get("gba_vc", {})
    if not isinstance(settings, dict):
        return False
    return all(
        raw and Path(raw).expanduser().is_file()
        for raw in (
            str(settings.get("boot_logo_path", "")).strip(),
            str(settings.get("donor_banner_path", "")).strip(),
        )
    )


def donor_readiness(config: dict, platform_slug: str) -> tuple[bool, str]:
    family = donor_family_for_platform(platform_slug)
    if family is None:
        return False, "Nintendo did not provide an implemented 3DS Virtual Console route for this platform."

    if family.injector_key == "classic_vc" and _cached_classic_runtime_ready(config, family.key):
        qualifier = " A New Nintendo 3DS is required." if family.requires_new_3ds else ""
        return True, f"{family.label} Virtual Console runtime is cached and ready.{qualifier}"
    if family.key == "gba" and _cached_gba_runtime_ready(config):
        return True, "Game Boy Advance donor assets are cached and ready."

    donor = configured_donor_path(config, family.key)
    if donor is None:
        return False, f"Configure a {family.label} Virtual Console donor CIA first."
    if family.requires_boot9 and configured_boot9_path(config) is None:
        return False, "Configure a valid retail boot9.bin/boot9_prot.bin dump first."
    if family.injector_key is None:
        return False, f"{family.label} donor is configured, but its family-specific injector is not implemented yet."
    if family.requires_new_3ds:
        return True, (
            f"{family.label} donor is configured. Donor preparation will resolve its public seed metadata; "
            "generated titles require a New Nintendo 3DS."
        )
    return True, f"{family.label} donor assets are configured."
