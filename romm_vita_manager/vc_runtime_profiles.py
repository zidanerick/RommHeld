from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VcDonorGuidance:
    family: str
    label: str
    classification: str
    recommendation: str
    details: tuple[str, ...]


_GUIDANCE: dict[str, VcDonorGuidance] = {
    "gba": VcDonorGuidance(
        family="gba",
        label="Game Boy Advance",
        classification="recommended",
        recommendation=(
            "Any genuine GBA Virtual Console donor is suitable for reusable AGB_FIRM "
            "boot-logo and presentation extraction."
        ),
        details=(
            "Nintendo's original GBA VC donor title IDs are not in the generated-inject F??? namespace.",
            "Donor choice is not used to emulate the target GBA game; AGB_FIRM provides the runtime.",
            "RommHeld validates the donor's ROM + 0x360-byte .CAA footer structure before caching assets.",
        ),
    ),
    "gb": VcDonorGuidance(
        family="gb",
        label="Game Boy",
        classification="profile-unverified",
        recommendation=(
            "Prefer a standard late retail Game Boy VC donor. Avoid special-purpose Pokemon VC "
            "runtimes as the general donor because their emulator behavior differs."
        ),
        details=(
            "A same-family donor is structurally required but does not guarantee identical emulator features.",
            "Unknown runtime fingerprints remain usable but are reported as unverified until hardware-tested.",
        ),
    ),
    "gbc": VcDonorGuidance(
        family="gbc",
        label="Game Boy Color",
        classification="profile-unverified",
        recommendation=(
            "Prefer a standard late retail Game Boy Color VC donor. Avoid special-purpose Pokemon VC "
            "runtimes as the general donor because their emulator behavior differs."
        ),
        details=(
            "RommHeld validates the embedded cartridge family before caching the runtime.",
            "Unknown runtime fingerprints remain usable but are reported as unverified until hardware-tested.",
        ),
    ),
    "nes": VcDonorGuidance(
        family="nes",
        label="NES",
        classification="hardware-retest-required",
        recommendation=(
            "Prefer a later standard retail NES VC donor rather than an early/Ambassador-era runtime. "
            "RommHeld records the runtime fingerprint and keeps unknown builds explicitly unverified."
        ),
        details=(
            "Nintendo shipped materially different NES VC emulator builds, including differences in save-state support.",
            "The current RommHeld NES package fixes require a fresh v5 donor cache and real-device launch/save/relaunch retest.",
        ),
    ),
    "gamegear": VcDonorGuidance(
        family="gamegear",
        label="Game Gear",
        classification="hardware-validation-required",
        recommendation=(
            "Use a genuine Game Gear Virtual Console donor whose .GG.m runtime structure is accepted by RommHeld. "
            "No runtime fingerprint should be labelled recommended until it passes real-device validation."
        ),
        details=(
            "RommHeld preserves the donor ROM filename because the MArchive cipher derives its key from that basename.",
            "Generated archives are round-trip checked on the PC, but the route still needs real-device launch validation.",
        ),
    ),
    "snes": VcDonorGuidance(
        family="snes",
        label="Super Nintendo",
        classification="experimental",
        recommendation=(
            "Use a genuine New Nintendo 3DS SNES VC donor. Donor choice does not replace per-game preset handling; "
            "generic simple LoROM/HiROM injection remains experimental."
        ),
        details=(
            "Enhancement-chip and unusual cartridge types are rejected to RetroArch instead of being guessed.",
            "The current generic preset path still requires real-device launch and SRAM save/relaunch validation.",
        ),
    ),
}


def guidance_for_family(family: str) -> VcDonorGuidance:
    key = family.strip().lower()
    try:
        return _GUIDANCE[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported Virtual Console donor guidance family: {family}") from exc


def _sha256(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


def _profile_id(family: str, parts: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    digest.update(b"rommheld-vc-runtime-profile-v1\0")
    digest.update(family.encode("ascii"))
    for part in parts:
        digest.update(b"\0")
        digest.update(part.encode("ascii"))
    return digest.hexdigest()[:16]


def build_classic_runtime_profile(
    family: str,
    donor_info: dict,
    *,
    code: bytes,
    exheader: bytes,
    romfs_template: bytes,
    rom_path: str,
    donor_banner: bytes | None = None,
    donor_icon: bytes | None = None,
    logo: bytes | None = None,
) -> dict:
    guidance = guidance_for_family(family)
    code_hash = _sha256(code)
    exheader_hash = _sha256(exheader)
    romfs_hash = _sha256(romfs_template)
    donor_title_id = str(donor_info.get("title_id", "")).strip().lower()
    profile_id = _profile_id(
        guidance.family,
        (code_hash, exheader_hash, rom_path, romfs_hash),
    )
    profile = {
        "version": 1,
        "family": guidance.family,
        "profile_id": profile_id,
        "classification": guidance.classification,
        "donor_title_id": donor_title_id,
        "code_sha256": code_hash,
        "exheader_sha256": exheader_hash,
        "romfs_template_sha256": romfs_hash,
        "rom_path": rom_path,
        "recommendation": guidance.recommendation,
    }
    # These fields were added after the v1 core fingerprint shipped. Keep them
    # optional so existing v1 profiles remain readable while newly prepared
    # caches cover every reusable presentation asset as well.
    if donor_banner is not None:
        profile["donor_banner_sha256"] = _sha256(donor_banner)
    if donor_icon is not None:
        profile["donor_icon_sha256"] = _sha256(donor_icon)
    if logo is not None:
        profile["logo_sha256"] = _sha256(logo)
    return profile


def _optional_hash_matches(profile: dict, field: str, data: bytes | None) -> bool:
    expected = profile.get(field)
    if expected is None:
        return True
    if not isinstance(expected, str) or data is None:
        return False
    return expected == _sha256(data)


def classic_runtime_profile_matches(
    profile: dict,
    family: str,
    *,
    code: bytes,
    exheader: bytes,
    romfs_template: bytes,
    rom_path: str,
    donor_banner: bytes | None = None,
    donor_icon: bytes | None = None,
    logo: bytes | None = None,
) -> bool:
    """Verify cached classic runtime bytes against a stored v1 fingerprint."""
    key = family.strip().lower()
    if profile.get("version") != 1 or str(profile.get("family", "")).lower() != key:
        return False
    code_hash = _sha256(code)
    exheader_hash = _sha256(exheader)
    romfs_hash = _sha256(romfs_template)
    expected_profile_id = _profile_id(key, (code_hash, exheader_hash, rom_path, romfs_hash))
    return (
        profile.get("code_sha256") == code_hash
        and profile.get("exheader_sha256") == exheader_hash
        and profile.get("romfs_template_sha256") == romfs_hash
        and profile.get("rom_path") == rom_path
        and profile.get("profile_id") == expected_profile_id
        and _optional_hash_matches(profile, "donor_banner_sha256", donor_banner)
        and _optional_hash_matches(profile, "donor_icon_sha256", donor_icon)
        and _optional_hash_matches(profile, "logo_sha256", logo)
    )


def build_gba_runtime_profile(
    donor_info: dict,
    *,
    boot_logo: bytes,
    donor_banner: bytes,
    donor_icon: bytes,
    donor_code_sha256: str,
    donor_rom_size: int,
) -> dict:
    guidance = guidance_for_family("gba")
    logo_hash = _sha256(boot_logo)
    banner_hash = _sha256(donor_banner)
    icon_hash = _sha256(donor_icon)
    donor_title_id = str(donor_info.get("title_id", "")).strip().lower()
    code_hash = donor_code_sha256.strip().lower()
    if len(code_hash) != 64 or any(ch not in "0123456789abcdef" for ch in code_hash):
        raise ValueError("GBA donor .code SHA-256 must contain exactly 64 hexadecimal digits.")
    if not 0 < donor_rom_size <= 0x2000000:
        raise ValueError("GBA donor ROM size is outside the 32 MiB cartridge limit.")
    profile_id = _profile_id(
        "gba",
        (donor_title_id, code_hash, str(donor_rom_size), logo_hash, banner_hash, icon_hash),
    )
    return {
        "version": 1,
        "family": "gba",
        "profile_id": profile_id,
        "classification": guidance.classification,
        "donor_title_id": donor_title_id,
        "donor_code_sha256": code_hash,
        "donor_rom_size": donor_rom_size,
        "boot_logo_sha256": logo_hash,
        "donor_banner_sha256": banner_hash,
        "donor_icon_sha256": icon_hash,
        "recommendation": guidance.recommendation,
    }


def gba_runtime_profile_matches(
    profile: dict,
    *,
    boot_logo: bytes,
    donor_banner: bytes,
    donor_icon: bytes,
) -> bool:
    """Verify reusable GBA cache assets covered by the stored donor profile."""
    if profile.get("version") != 1 or str(profile.get("family", "")).lower() != "gba":
        return False
    return (
        profile.get("boot_logo_sha256") == _sha256(boot_logo)
        and profile.get("donor_banner_sha256") == _sha256(donor_banner)
        and profile.get("donor_icon_sha256") == _sha256(donor_icon)
    )


def configured_runtime_profile(config: dict, family: str) -> dict | None:
    key = family.strip().lower()
    if key == "gba":
        root = config.get("gba_vc", {})
        value = root.get("runtime_profile") if isinstance(root, dict) else None
    else:
        root = config.get("classic_vc", {})
        entry = root.get(key, {}) if isinstance(root, dict) else {}
        value = entry.get("runtime_profile") if isinstance(entry, dict) else None
    return dict(value) if isinstance(value, dict) else None
