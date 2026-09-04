from __future__ import annotations

from pathlib import Path

from .config import package_cache_dir, save_config
from .gba_vc import (
    extract_native_boot_logo,
    extract_native_donor_banner,
    extract_native_donor_icon,
)
from .vc_donors import configure_boot9, configure_donor


BOOT_LOGO_FILENAME = "agb_firm_boot_logo.bin"
DONOR_BANNER_FILENAME = "gba_vc_donor_banner.bin"
DONOR_ICON_FILENAME = "gba_vc_donor_icon.smdh"


def cached_boot_logo_path() -> Path:
    return package_cache_dir() / BOOT_LOGO_FILENAME


def cached_donor_banner_path() -> Path:
    return package_cache_dir() / DONOR_BANNER_FILENAME


def cached_donor_icon_path() -> Path:
    return package_cache_dir() / DONOR_ICON_FILENAME


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


def configured_donor_icon(config: dict) -> Path | None:
    settings = config.get("gba_vc", {})
    if not isinstance(settings, dict):
        return None
    raw = str(settings.get("donor_icon_path", "")).strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.is_file() else None


def save_gba_vc_asset_paths(
    config: dict,
    *,
    boot_logo: Path | None = None,
    donor_banner: Path | None = None,
    donor_icon: Path | None = None,
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
    if donor_icon is not None:
        settings["donor_icon_path"] = str(donor_icon.expanduser())
    updated["gba_vc"] = settings
    save_config(updated)
    return updated


def _forget_gba_donor_sources(config: dict) -> dict:
    """Drop donor/boot9 source paths once reusable cache files exist.

    The extracted boot logo, animated banner and SMDH icon are sufficient for
    subsequent GBA packaging. Keeping source paths after a successful one-time
    preparation only makes the deployment UI look as if the original CIA or
    boot9 are still required.
    """
    updated = dict(config)
    vc = (
        dict(updated.get("three_ds_vc", {}))
        if isinstance(updated.get("three_ds_vc", {}), dict)
        else {}
    )
    vc.pop("boot9_path", None)
    vc.pop("boot9_variant", None)
    donors = dict(vc.get("donors", {})) if isinstance(vc.get("donors", {}), dict) else {}
    gba = dict(donors.get("gba", {})) if isinstance(donors.get("gba", {}), dict) else {}
    gba.pop("cia_path", None)
    if gba:
        donors["gba"] = gba
    else:
        donors.pop("gba", None)
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


def _write_cached_asset(destination: Path, data: bytes) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(destination)
    return destination


def extract_and_cache_boot_logo(config: dict, donor_cia: Path, boot9: Path) -> Path:
    donor_cia = donor_cia.expanduser()
    boot9 = boot9.expanduser()
    if not donor_cia.is_file():
        raise FileNotFoundError(f"Donor CIA does not exist: {donor_cia}")
    if not boot9.is_file():
        raise FileNotFoundError(f"boot9 dump does not exist: {boot9}")

    destination = _write_cached_asset(
        cached_boot_logo_path(), extract_native_boot_logo(donor_cia, boot9)
    )
    save_gba_vc_asset_paths(config, boot_logo=destination)
    return destination


def extract_and_cache_gba_donor_assets(
    config: dict, donor_cia: Path, boot9: Path
) -> tuple[dict, Path, Path]:
    """Validate a GBA VC donor and cache its reusable official presentation.

    The donor CIA and boot9 dump are one-time inputs. RommHeld retains the
    AGB_FIRM boot logo, animated banner and SMDH icon frame, then forgets the
    original source paths. The donor binaries themselves are never bundled in
    the application or repository.
    """
    donor_cia = donor_cia.expanduser()
    boot9 = boot9.expanduser()
    updated = configure_boot9(config, boot9)
    updated = configure_donor(updated, "gba", donor_cia)

    logo = _write_cached_asset(
        cached_boot_logo_path(), extract_native_boot_logo(donor_cia, boot9)
    )
    banner = _write_cached_asset(
        cached_donor_banner_path(), extract_native_donor_banner(donor_cia, boot9)
    )
    icon = _write_cached_asset(
        cached_donor_icon_path(), extract_native_donor_icon(donor_cia, boot9)
    )
    updated = save_gba_vc_asset_paths(
        updated,
        boot_logo=logo,
        donor_banner=banner,
        donor_icon=icon,
    )
    updated = _forget_gba_donor_sources(updated)
    return updated, logo, banner
