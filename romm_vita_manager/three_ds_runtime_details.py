from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .three_ds_apps import APP_BY_KEY, detect_three_ds_app
from .three_ds_targets import RETROACHIEVEMENTS_RETROARCH_PLATFORM_SLUGS


@dataclass(frozen=True)
class FirmwareRequirement:
    key: str
    filenames: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class RetroArchCoreProfile:
    platform_slug: str
    core_ids: tuple[str, ...]
    achievement_core_ids: tuple[str, ...] = ()
    firmware: tuple[FirmwareRequirement, ...] = ()

    @property
    def retroachievements_recommended(self) -> bool:
        return self.platform_slug in RETROACHIEVEMENTS_RETROARCH_PLATFORM_SLUGS


@dataclass(frozen=True)
class RetroArchRouteStatus:
    profile: RetroArchCoreProfile | None
    frontend_detected: bool
    active_core_files: tuple[Path, ...]
    inactive_core_files: tuple[Path, ...]
    system_directory: Path | None
    found_firmware: tuple[str, ...]
    missing_firmware: tuple[FirmwareRequirement, ...]

    @property
    def state(self) -> str:
        if not self.frontend_detected:
            return "frontend_not_detected"
        if self.profile is None:
            return "profile_unverified"
        if not self.active_core_files:
            if self.inactive_core_files:
                return "core_staged_inactive"
            return "confirm_core_on_console"
        if self.profile.firmware and self.system_directory is None:
            return "firmware_unverified"
        if self.missing_firmware:
            return "missing_firmware"
        if any(path.suffix.casefold() == ".3dsx" for path in self.active_core_files):
            return "launchable_sd_core_detected"
        return "core_installer_evidence"

    @property
    def note(self) -> str:
        if self.state == "frontend_not_detected":
            return "RetroArch SD-side frontend evidence was not found."
        if self.state == "profile_unverified":
            return "RetroArch is present, but RommHeld has no audited 3DS core profile for this platform."
        if self.state == "core_staged_inactive":
            return "A matching core package exists only in the inactive core directory."
        if self.state == "confirm_core_on_console":
            return "No matching core package is visible on SD. A CIA-installed core may still be present, so confirm on the console."
        if self.state == "firmware_unverified":
            names = ", ".join(req.description for req in self.profile.firmware) if self.profile else "required firmware"
            return f"A matching core is present, but RetroArch's System/BIOS directory is not explicit, so RommHeld cannot verify {names}."
        if self.state == "missing_firmware":
            names = ", ".join(req.description for req in self.missing_firmware)
            return f"A matching core is present, but required firmware is missing: {names}."
        if self.state == "launchable_sd_core_detected":
            return "A matching 3DSX core executable is present in the active RetroArch core directory."
        return "A matching CIA core package is present. Confirm on the console that the core title is installed."


@dataclass(frozen=True)
class TwilightRuntimeStatus:
    twilight_assets: bool
    nds_bootstrap: bool
    boot_nds: bool

    @property
    def state(self) -> str:
        if self.twilight_assets and self.nds_bootstrap:
            return "ready"
        if self.twilight_assets or self.nds_bootstrap or self.boot_nds:
            return "incomplete"
        return "not_detected"

    @property
    def note(self) -> str:
        if self.state == "ready":
            suffix = " BOOT.NDS is also present." if self.boot_nds else ""
            return f"TWiLight Menu++ assets and nds-bootstrap are present.{suffix}"
        if self.state == "incomplete":
            missing: list[str] = []
            if not self.twilight_assets:
                missing.append("TWiLight Menu++ assets")
            if not self.nds_bootstrap:
                missing.append("nds-bootstrap")
            return "The NDS runtime is incomplete; missing " + " and ".join(missing) + "."
        return "No coherent TWiLight Menu++ / nds-bootstrap runtime was found."


# Core IDs are limited to routes present in libretro-super's current
# recipes/nintendo/3ds build recipe. This keeps SD-side readiness evidence tied
# to cores that are actually produced for Nintendo 3DS rather than to generic
# Libretro metadata or historical package definitions.
RETROARCH_CORE_PROFILES: dict[str, RetroArchCoreProfile] = {
    "gba": RetroArchCoreProfile("gba", ("mgba", "gpsp"), ("mgba",)),
    "gb": RetroArchCoreProfile(
        "gb",
        ("gambatte", "mgba", "tgbdual", "doublecherrygb"),
        ("gambatte", "mgba"),
    ),
    "gbc": RetroArchCoreProfile(
        "gbc",
        ("gambatte", "mgba", "tgbdual", "doublecherrygb"),
        ("gambatte", "mgba"),
    ),
    "nes": RetroArchCoreProfile(
        "nes",
        ("fceumm", "quicknes", "nestopia"),
        ("fceumm", "quicknes"),
    ),
    "famicom": RetroArchCoreProfile(
        "famicom",
        ("fceumm", "quicknes", "nestopia"),
        ("fceumm", "quicknes"),
    ),
    "fds": RetroArchCoreProfile(
        "fds",
        ("fceumm",),
        ("fceumm",),
        (
            FirmwareRequirement(
                "fds-bios",
                ("disksys.rom",),
                "Famicom Disk System BIOS (disksys.rom)",
            ),
        ),
    ),
    "snes": RetroArchCoreProfile(
        "snes",
        ("snes9x2002", "snes9x2005", "snes9x2005_plus", "snes9x2010", "chimerasnes"),
        (),
    ),
    "gamegear": RetroArchCoreProfile(
        "gamegear",
        ("genesis_plus_gx", "smsplus"),
        ("genesis_plus_gx",),
    ),
    "sms": RetroArchCoreProfile(
        "sms",
        ("genesis_plus_gx", "picodrive", "smsplus"),
        ("genesis_plus_gx", "picodrive", "smsplus"),
    ),
    "genesis": RetroArchCoreProfile(
        "genesis",
        ("genesis_plus_gx", "picodrive", "clownmdemu"),
        ("genesis_plus_gx", "picodrive", "clownmdemu"),
    ),
    "sega32": RetroArchCoreProfile("sega32", ("picodrive",), ("picodrive",)),
    "segacd": RetroArchCoreProfile(
        "segacd",
        ("genesis_plus_gx", "picodrive"),
        ("genesis_plus_gx", "picodrive"),
        (
            FirmwareRequirement(
                "segacd-bios",
                ("bios_CD_U.bin", "bios_CD_E.bin", "bios_CD_J.bin"),
                "a Sega/Mega CD BIOS matching the game's region",
            ),
        ),
    ),
    "msx": RetroArchCoreProfile("msx", ("bluemsx", "fmsx")),
    "msx2": RetroArchCoreProfile("msx2", ("bluemsx", "fmsx")),
    "atari5200": RetroArchCoreProfile(
        "atari5200",
        ("atari800",),
        (),
        (
            FirmwareRequirement(
                "atari-5200-bios",
                ("5200.rom",),
                "Atari 5200 BIOS (5200.rom)",
            ),
        ),
    ),
    "atari7800": RetroArchCoreProfile("atari7800", ("prosystem",)),
    "lynx": RetroArchCoreProfile("lynx", ("handy",)),
    "vectrex": RetroArchCoreProfile("vectrex", ("vecx",)),
    "colecovision": RetroArchCoreProfile("colecovision", ("bluemsx",)),
    "c64": RetroArchCoreProfile("c64", ("vice_x64", "vice_x64sc", "frodo")),
    "dos": RetroArchCoreProfile("dos", ("dosbox_svn",)),
    "wonderswan": RetroArchCoreProfile("wonderswan", ("mednafen_wswan",)),
    "wonderswan-color": RetroArchCoreProfile(
        "wonderswan-color",
        ("mednafen_wswan",),
    ),
    "neogeomvs": RetroArchCoreProfile(
        "neogeomvs",
        ("fbalpha2012_neogeo", "fbneo"),
    ),
    "neo-geo-pocket": RetroArchCoreProfile(
        "neo-geo-pocket",
        ("mednafen_ngp", "race"),
    ),
    "neo-geo-pocket-color": RetroArchCoreProfile(
        "neo-geo-pocket-color",
        ("mednafen_ngp", "race"),
    ),
    "zxs": RetroArchCoreProfile("zxs", ("fuse",)),
    "turbografx-cd": RetroArchCoreProfile(
        "turbografx-cd",
        ("mednafen_pce_fast",),
        (),
        (
            FirmwareRequirement(
                "pce-cd-bios",
                ("syscard3.pce", "syscard2.pce", "syscard1.pce", "gexpress.pce"),
                "a PC Engine/TurboGrafx-CD System Card BIOS",
            ),
        ),
    ),
    "virtualboy": RetroArchCoreProfile(
        "virtualboy",
        ("mednafen_vb",),
        ("mednafen_vb",),
    ),
}


def _casefold_child(directory: Path, name: str) -> Path | None:
    if not directory.is_dir():
        return None
    try:
        wanted = name.casefold()
        return next((entry for entry in directory.iterdir() if entry.name.casefold() == wanted), None)
    except OSError:
        return None


def _casefold_path(root: Path, relative: str) -> Path | None:
    current = root
    for part in Path(relative).parts:
        match = _casefold_child(current, part)
        if match is None:
            return None
        current = match
    return current


def _config_value(root: Path, key: str) -> str | None:
    config = _casefold_path(root, "RetroArch/retroarch.cfg")
    if config is None or not config.is_file():
        return None
    try:
        lines = config.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    prefix = key.casefold()
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        raw_key, raw_value = line.split("=", 1)
        if raw_key.strip().casefold() != prefix:
            continue
        return raw_value.strip().strip('"').strip("'")
    return None


def _resolve_config_path(root: Path, value: str | None) -> Path | None:
    if not value or value.casefold() == "default":
        return None
    normalized = value.replace("\\", "/").strip()
    if normalized.casefold().startswith("sdmc:"):
        normalized = normalized[5:]
    normalized = normalized.lstrip("/")
    if not normalized:
        return root
    return root / normalized


def _core_directories(root: Path) -> tuple[Path, Path]:
    configured = _resolve_config_path(root, _config_value(root, "libretro_directory"))
    active = configured or root / "RetroArch" / "Cores"
    inactive = active.parent / "Cores-Notused"
    return active, inactive


def _matching_core_files(directory: Path, core_ids: tuple[str, ...]) -> tuple[Path, ...]:
    if not directory.is_dir():
        return ()
    wanted = {
        f"{core}_libretro{suffix}".casefold()
        for core in core_ids
        for suffix in (".cia", ".3dsx")
    }
    try:
        return tuple(
            sorted(
                (entry for entry in directory.iterdir() if entry.is_file() and entry.name.casefold() in wanted),
                key=lambda path: path.name.casefold(),
            )
        )
    except OSError:
        return ()


def _firmware_status(
    root: Path,
    requirements: tuple[FirmwareRequirement, ...],
) -> tuple[Path | None, tuple[str, ...], tuple[FirmwareRequirement, ...]]:
    system_directory = _resolve_config_path(root, _config_value(root, "system_directory"))
    if not requirements or system_directory is None:
        return system_directory, (), ()

    found: list[str] = []
    missing: list[FirmwareRequirement] = []
    for requirement in requirements:
        matched = next(
            (
                filename
                for filename in requirement.filenames
                if _casefold_child(system_directory, filename) is not None
            ),
            None,
        )
        if matched is None:
            missing.append(requirement)
        else:
            found.append(matched)
    return system_directory, tuple(found), tuple(missing)


def scan_retroarch_route(root: Path, platform_slug: str) -> RetroArchRouteStatus:
    root = root.expanduser()
    profile = RETROARCH_CORE_PROFILES.get(platform_slug.casefold())
    frontend = detect_three_ds_app(root, APP_BY_KEY["retroarch"]).detected
    if profile is None:
        return RetroArchRouteStatus(profile, frontend, (), (), None, (), ())

    active_directory, inactive_directory = _core_directories(root)
    active = _matching_core_files(active_directory, profile.core_ids)
    inactive = _matching_core_files(inactive_directory, profile.core_ids)
    system_directory, found_firmware, missing_firmware = _firmware_status(root, profile.firmware)
    return RetroArchRouteStatus(
        profile,
        frontend,
        active,
        inactive,
        system_directory,
        found_firmware,
        missing_firmware,
    )


def scan_twilight_runtime(root: Path) -> TwilightRuntimeStatus:
    root = root.expanduser()
    return TwilightRuntimeStatus(
        twilight_assets=_casefold_path(root, "_nds/TWiLightMenu") is not None,
        nds_bootstrap=_casefold_path(root, "_nds/nds-bootstrap") is not None,
        boot_nds=_casefold_path(root, "BOOT.NDS") is not None,
    )
