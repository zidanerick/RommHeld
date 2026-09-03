from __future__ import annotations

from pathlib import Path

from .config import package_cache_dir, save_config
from .gba_vc import extract_native_boot_logo


BOOT_LOGO_FILENAME = "agb_firm_boot_logo.bin"


def cached_boot_logo_path() -> Path:
    return package_cache_dir() / BOOT_LOGO_FILENAME


def configured_boot_logo(config: dict) -> Path | None:
    settings = config.get("gba_vc", {})
    if not isinstance(settings, dict):
        return None
    raw = str(settings.get("boot_logo_path", "")).strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.is_file() else None


def configured_donor_banner(config: dict) -> Path | None:
    settings = config.get("gba_vc", {})
    if not isinstance(settings, dict):
        return None
    raw = str(settings.get("donor_banner_path", "")).strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.is_file() else None


def save_gba_vc_asset_paths(
    config: dict,
    *,
    boot_logo: Path | None = None,
    donor_banner: Path | None = None,
) -> dict:
    updated = dict(config)
    settings = (
        dict(updated.get("gba_vc", {}))
        if isinstance(updated.get("gba_vc", {}), dict)
        else {}
    )
    if boot_logo is not None:
        settings["boot_logo_path"] = str(boot_logo.expanduser())
    if donor_banner is not None:
        settings["donor_banner_path"] = str(donor_banner.expanduser())
    updated["gba_vc"] = settings
    save_config(updated)
    return updated


def extract_and_cache_boot_logo(config: dict, donor_cia: Path, boot9: Path) -> Path:
    donor_cia = donor_cia.expanduser()
    boot9 = boot9.expanduser()
    if not donor_cia.is_file():
        raise FileNotFoundError(f"Donor CIA does not exist: {donor_cia}")
    if not boot9.is_file():
        raise FileNotFoundError(f"boot9 dump does not exist: {boot9}")

    logo = extract_native_boot_logo(donor_cia, boot9)
    destination = cached_boot_logo_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_bytes(logo)
    temporary.replace(destination)

    save_gba_vc_asset_paths(config, boot_logo=destination)
    return destination
