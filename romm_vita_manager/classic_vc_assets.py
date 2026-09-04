from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .classic_vc import ClassicVcRuntime, extract_classic_vc_runtime
from .config import package_cache_dir, save_config
from .vc_donors import configure_boot9, configure_donor

_SUPPORTED = {"gb", "gbc"}


@dataclass(frozen=True)
class ClassicVcRuntimePaths:
    family: str
    exheader: Path
    code: Path
    logo: Path | None
    romfs_template: Path
    rom_path: str

    def load(self) -> ClassicVcRuntime:
        return ClassicVcRuntime(
            family=self.family,
            exheader=self.exheader.read_bytes(),
            code=self.code.read_bytes(),
            logo=self.logo.read_bytes() if self.logo is not None else b"",
            romfs_template=self.romfs_template.read_bytes(),
            rom_path=self.rom_path,
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


def configured_classic_runtime(config: dict, family: str) -> ClassicVcRuntimePaths | None:
    family = _family_key(family)
    root = config.get("classic_vc", {})
    entry = root.get(family, {}) if isinstance(root, dict) else {}
    if not isinstance(entry, dict):
        return None
    exheader = Path(str(entry.get("exheader_path", ""))).expanduser()
    code = Path(str(entry.get("code_path", ""))).expanduser()
    romfs = Path(str(entry.get("romfs_template_path", ""))).expanduser()
    rom_path = str(entry.get("rom_path", "")).strip()
    logo_raw = str(entry.get("logo_path", "")).strip()
    logo = Path(logo_raw).expanduser() if logo_raw else None
    if not exheader.is_file() or not code.is_file() or not romfs.is_file() or not rom_path:
        return None
    if logo is not None and not logo.is_file():
        return None
    return ClassicVcRuntimePaths(
        family=family,
        exheader=exheader,
        code=code,
        logo=logo,
        romfs_template=romfs,
        rom_path=rom_path,
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
    runtime = extract_classic_vc_runtime(donor_cia, boot9, family)

    cache = runtime_cache_dir(family)
    exheader = _write(cache / "exheader.bin", runtime.exheader)
    code = _write(cache / "code.bin", runtime.code)
    romfs = _write(cache / "romfs_template.bin", runtime.romfs_template)
    logo = _write(cache / "logo.bin", runtime.logo) if runtime.logo else None

    root = dict(updated.get("classic_vc", {})) if isinstance(updated.get("classic_vc", {}), dict) else {}
    root[family] = {
        "exheader_path": str(exheader),
        "code_path": str(code),
        "romfs_template_path": str(romfs),
        "logo_path": str(logo) if logo is not None else "",
        "rom_path": runtime.rom_path,
    }
    updated["classic_vc"] = root
    save_config(updated)
    updated = _forget_sources(updated, family)
    paths = configured_classic_runtime(updated, family)
    if paths is None:
        raise RuntimeError("Classic VC runtime cache was written but could not be reopened.")
    return updated, paths
