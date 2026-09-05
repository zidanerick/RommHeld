from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .classic_vc import ClassicVcRuntime, extract_classic_vc_runtime
from .classic_vc_hardware_fix import validate_retail_romfs
from .classic_vc_ncch_regions import (
    auxiliary_cache_paths,
    extract_ncch_auxiliary_regions,
)
from .config import package_cache_dir, save_config
from .gba_vc import _primary_ncch_from_cia
from .vc_donors import configure_boot9, configure_donor, configured_donor_info
from .vc_runtime_profiles import build_classic_runtime_profile, classic_runtime_profile_matches

_SUPPORTED = {"gb", "gbc", "nes", "gamegear", "snes"}
# Version 5 adds the donor's optional NCCH plain and dedicated launch-logo
# regions. NES and SNES retail donors use the dedicated logo region, so their
# older caches must be refreshed. GB/GBC/Game Gear had no dedicated NCCH logo
# in the supplied retail donors and may keep a validated v4 cache; they will be
# upgraded naturally the next time their donor is prepared.
_CACHE_VERSION = 5
_LOGO_REGION_FAMILIES = {"nes", "snes"}


@dataclass(frozen=True)
class ClassicVcRuntimePaths:
    family: str
    exheader: Path
    code: Path
    logo: Path | None
    donor_banner: Path
    donor_icon: Path
    romfs_template: Path
    rom_path: str
    ncch_plain: Path | None = None
    ncch_logo: Path | None = None

    def load(self) -> ClassicVcRuntime:
        romfs = self.romfs_template.read_bytes()
        validate_retail_romfs(romfs)
        return ClassicVcRuntime(
            family=self.family,
            exheader=self.exheader.read_bytes(),
            code=self.code.read_bytes(),
            logo=self.logo.read_bytes() if self.logo is not None else b"",
            romfs_template=romfs,
            rom_path=self.rom_path,
            donor_banner=self.donor_banner.read_bytes(),
            donor_icon=self.donor_icon.read_bytes(),
        )


def _family_key(family: str) -> str:
    key = family.lower()
    if key not in _SUPPORTED:
        raise ValueError(f"Unsupported cached classic VC family: {family}")
    return key


def runtime_cache_dir(family: str) -> Path:
    return package_cache_dir() / "classic_vc" / _family_key(family)


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)
    return path


def _write_optional(path: Path, data: bytes) -> Path | None:
    if data:
        return _write(path, data)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    return None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _optional_region_hash_matches(entry: dict, path: Path | None, field: str) -> bool:
    expected = str(entry.get(field, "")).strip().lower()
    if not expected:
        # Existing v5 caches predate persisted auxiliary hashes. Preserve that
        # compatibility contract; newly prepared caches always store hashes.
        return True
    if path is None or not path.is_file():
        return False
    if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
        return False
    try:
        return _sha256(path.read_bytes()) == expected
    except OSError:
        return False


def configured_classic_runtime(config: dict, family: str) -> ClassicVcRuntimePaths | None:
    family = _family_key(family)
    root = config.get("classic_vc", {})
    entry = root.get(family, {}) if isinstance(root, dict) else {}
    if not isinstance(entry, dict):
        return None
    cache_version = entry.get("cache_version")
    if family in _LOGO_REGION_FAMILIES:
        if cache_version != _CACHE_VERSION:
            return None
    elif cache_version not in (4, _CACHE_VERSION):
        return None
    exheader = Path(str(entry.get("exheader_path", ""))).expanduser()
    code = Path(str(entry.get("code_path", ""))).expanduser()
    romfs = Path(str(entry.get("romfs_template_path", ""))).expanduser()
    rom_path = str(entry.get("rom_path", "")).strip()
    logo_raw = str(entry.get("logo_path", "")).strip()
    logo = Path(logo_raw).expanduser() if logo_raw else None
    banner_raw = str(entry.get("donor_banner_path", "")).strip()
    donor_banner = Path(banner_raw).expanduser() if banner_raw else None
    icon_raw = str(entry.get("donor_icon_path", "")).strip()
    donor_icon = Path(icon_raw).expanduser() if icon_raw else None
    plain_raw = str(entry.get("ncch_plain_path", "")).strip()
    ncch_plain = Path(plain_raw).expanduser() if plain_raw else None
    ncch_logo_raw = str(entry.get("ncch_logo_path", "")).strip()
    ncch_logo = Path(ncch_logo_raw).expanduser() if ncch_logo_raw else None
    if not exheader.is_file() or not code.is_file() or not romfs.is_file() or not rom_path:
        return None
    if logo is not None and not logo.is_file():
        return None
    if donor_banner is None or not donor_banner.is_file():
        return None
    if donor_icon is None or not donor_icon.is_file():
        return None
    if ncch_plain is not None and not ncch_plain.is_file():
        return None
    if ncch_logo is not None and not ncch_logo.is_file():
        return None
    if ncch_logo is not None and ncch_logo.stat().st_size != 0x2000:
        return None
    if not _optional_region_hash_matches(entry, ncch_plain, "ncch_plain_sha256"):
        return None
    if not _optional_region_hash_matches(entry, ncch_logo, "ncch_logo_sha256"):
        return None
    # A v5 NES/SNES cache must actually contain the dedicated retail launch
    # logo captured from its donor. Otherwise accepting the cache would defeat
    # the purpose of the format bump and recreate the minimal NCCH layout.
    if family in _LOGO_REGION_FAMILIES and ncch_logo is None:
        return None
    try:
        romfs_bytes = romfs.read_bytes()
        validate_retail_romfs(romfs_bytes)
        profile = entry.get("runtime_profile")
        if isinstance(profile, dict) and not classic_runtime_profile_matches(
            profile,
            family,
            code=code.read_bytes(),
            exheader=exheader.read_bytes(),
            romfs_template=romfs_bytes,
            rom_path=rom_path,
        ):
            return None
    except (OSError, ValueError):
        return None
    return ClassicVcRuntimePaths(
        family=family,
        exheader=exheader,
        code=code,
        logo=logo,
        donor_banner=donor_banner,
        donor_icon=donor_icon,
        romfs_template=romfs,
        rom_path=rom_path,
        ncch_plain=ncch_plain,
        ncch_logo=ncch_logo,
    )


def _forget_sources(config: dict, family: str) -> dict:
    updated = dict(config)
    vc = dict(updated.get("three_ds_vc", {})) if isinstance(updated.get("three_ds_vc", {}), dict) else {}
    vc.pop("boot9_path", None)
    vc.pop("boot9_variant", None)
    donors = dict(vc.get("donors", {})) if isinstance(vc.get("donors", {}), dict) else {}
    entry = dict(donors.get(family, {})) if isinstance(donors.get(family, {}), dict) else {}
    entry.pop("cia_path", None)
    if entry:
        donors[family] = entry
    else:
        donors.pop(family, None)
    if donors:
        vc["donors"] = donors
    else:
        vc.pop("donors", None)
    if vc:
        updated["three_ds_vc"] = vc
    else:
        updated.pop("three_ds_vc", None)
    save_config(updated)
    return updated


def extract_and_cache_classic_runtime(
    config: dict,
    family: str,
    donor_cia: Path,
    boot9: Path,
) -> tuple[dict, ClassicVcRuntimePaths]:
    family = _family_key(family)
    donor_cia = donor_cia.expanduser()
    boot9 = boot9.expanduser()
    updated = configure_boot9(config, boot9)
    updated = configure_donor(updated, family, donor_cia)

    donor_bytes = donor_cia.read_bytes()
    donor_ncch = _primary_ncch_from_cia(donor_bytes)
    auxiliary = extract_ncch_auxiliary_regions(donor_ncch)
    runtime = extract_classic_vc_runtime(donor_cia, boot9, family)

    if not getattr(runtime, "donor_banner", b""):
        raise RuntimeError("Virtual Console donor did not provide an animated HOME Menu banner.")
    if not getattr(runtime, "donor_icon", b""):
        raise RuntimeError("Virtual Console donor did not provide a HOME Menu SMDH icon.")
    if family in _LOGO_REGION_FAMILIES and not auxiliary.logo:
        raise RuntimeError(
            f"{family.upper()} Virtual Console donor is missing its dedicated retail NCCH launch logo."
        )
    validate_retail_romfs(runtime.romfs_template)
    runtime_profile = build_classic_runtime_profile(
        family,
        configured_donor_info(updated, family),
        code=runtime.code,
        exheader=runtime.exheader,
        romfs_template=runtime.romfs_template,
        rom_path=runtime.rom_path,
    )

    cache = runtime_cache_dir(family)
    exheader = _write(cache / "exheader.bin", runtime.exheader)
    code = _write(cache / "code.bin", runtime.code)
    romfs = _write(cache / "romfs_template.bin", runtime.romfs_template)
    logo = _write(cache / "logo.bin", runtime.logo) if runtime.logo else None
    donor_banner = _write(cache / "donor_banner.bin", runtime.donor_banner)
    donor_icon = _write(cache / "donor_icon.smdh", runtime.donor_icon)
    plain_cache, logo_cache = auxiliary_cache_paths(family)
    ncch_plain = _write_optional(plain_cache, auxiliary.plain)
    ncch_logo = _write_optional(logo_cache, auxiliary.logo)

    root = dict(updated.get("classic_vc", {})) if isinstance(updated.get("classic_vc", {}), dict) else {}
    root[family] = {
        "cache_version": _CACHE_VERSION,
        "exheader_path": str(exheader),
        "code_path": str(code),
        "romfs_template_path": str(romfs),
        "logo_path": str(logo) if logo is not None else "",
        "donor_banner_path": str(donor_banner),
        "donor_icon_path": str(donor_icon),
        "ncch_plain_path": str(ncch_plain) if ncch_plain is not None else "",
        "ncch_plain_sha256": _sha256(auxiliary.plain) if auxiliary.plain else "",
        "ncch_logo_path": str(ncch_logo) if ncch_logo is not None else "",
        "ncch_logo_sha256": _sha256(auxiliary.logo) if auxiliary.logo else "",
        "rom_path": runtime.rom_path,
        "runtime_profile": runtime_profile,
    }
    updated["classic_vc"] = root
    save_config(updated)
    updated = _forget_sources(updated, family)
    paths = configured_classic_runtime(updated, family)
    if paths is None:
        raise RuntimeError("Virtual Console runtime cache was written but failed structural validation.")
    return updated, paths
