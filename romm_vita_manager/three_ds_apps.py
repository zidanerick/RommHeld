from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .three_ds_targets import RETROARCH_TARGET_PLATFORM_SLUGS
from .three_ds_title_inventory import mounted_sd_title_ids


@dataclass(frozen=True)
class ThreeDSAppDefinition:
    key: str
    name: str
    role: str
    description: str
    markers: tuple[str, ...]
    upstream_url: str
    install_policy: str
    platform_slugs: tuple[str, ...] = ()
    installed_title_may_exist_without_sd_marker: bool = False
    marker_policy: str = "any"
    installed_title_ids: tuple[str, ...] = ()
    marker_confirms_launchable: bool = True

    def __post_init__(self) -> None:
        if self.marker_policy not in {"any", "all"}:
            raise ValueError(f"Unknown marker policy: {self.marker_policy}")
        for raw_title_id in self.installed_title_ids:
            title_id = raw_title_id.strip()
            if len(title_id) != 16 or any(
                character not in "0123456789abcdefABCDEF" for character in title_id
            ):
                raise ValueError(
                    f"Invalid installed Title ID for {self.key}: {raw_title_id!r}"
                )


@dataclass(frozen=True)
class ThreeDSAppStatus:
    definition: ThreeDSAppDefinition
    detected: bool
    marker: str | None = None
    title_id: str | None = None
    source: str = "mounted_sd"

    @property
    def state(self) -> str:
        return "detected" if self.detected else "not_detected"

    @property
    def detection_note(self) -> str:
        if self.source == "unchecked":
            return "No mounted-SD or live-FTP inventory has been checked yet."
        if self.detected and self.source == "ftp_live":
            return "A live ftpd connection is active on the console."
        if self.detected and self.title_id:
            if self.source == "ftp":
                return (
                    "Installed CIA title is visible in the live FTP SD title tree: "
                    f"{self.title_id}."
                )
            return (
                "Installed CIA title is visible in the mounted SD title tree: "
                f"{self.title_id}."
            )
        if self.detected and self.marker:
            if self.source == "ftp":
                return f"Live FTP evidence found at {self.marker}."
            return f"SD evidence found at {self.marker}."
        if self.marker and not self.definition.marker_confirms_launchable:
            if self.source == "ftp":
                return (
                    f"Runtime files are visible over FTP at {self.marker}, but these files do not "
                    "prove that a launchable frontend or HOME Menu title is installed."
                )
            return (
                f"Runtime files are present at {self.marker}, but these files do not prove that "
                "a launchable frontend or HOME Menu title is installed."
            )
        if self.definition.installed_title_may_exist_without_sd_marker:
            if self.source == "ftp":
                return (
                    "No known FTP-visible SD marker was found; an installed CIA title may "
                    "still be present on the console."
                )
            return "No SD marker was found; an installed CIA title may still be present on the console."
        if self.source == "ftp":
            return "No known FTP-visible SD marker was found."
        return "No known SD marker was found."


THREE_DS_APPS: tuple[ThreeDSAppDefinition, ...] = (
    ThreeDSAppDefinition(
        "luma",
        "Luma3DS",
        "foundation",
        "Custom firmware foundation used by the supported 3DS homebrew workflows.",
        ("boot.firm", "luma/config.ini", "luma"),
        "https://github.com/LumaTeam/Luma3DS/releases",
        "guide_only",
    ),
    ThreeDSAppDefinition(
        "homebrew-launcher",
        "Homebrew Launcher environment",
        "foundation",
        "Homebrew entry environment. RommHeld only checks SD-side evidence and does not attempt to modify the console exploit chain.",
        ("boot.3dsx",),
        "https://3ds.hacks.guide/finalizing-setup.html",
        "guide_only",
    ),
    ThreeDSAppDefinition(
        "fbi",
        "FBI",
        "installer",
        "Title manager used by RommHeld's CIA and Remote Install workflows.",
        ("3ds/FBI/FBI.3dsx", "3ds/fbi/fbi.3dsx", "FBI.3dsx"),
        "https://github.com/Steveice10/FBI/releases",
        "manual_or_existing",
        installed_title_may_exist_without_sd_marker=True,
        installed_title_ids=("000400000F800100",),
    ),
    ThreeDSAppDefinition(
        "ftpd",
        "ftpd",
        "transfer",
        "FTP server used for RommHeld filesystem transfers over the local network.",
        ("3ds/ftpd/ftpd.3dsx", "3ds/ftpd.3dsx", "3ds/FTPD/FTPD.3dsx"),
        "https://github.com/mtheall/ftpd/releases",
        "universal_updater_or_manual",
        installed_title_may_exist_without_sd_marker=True,
        installed_title_ids=("000400000BEEF500",),
    ),
    ThreeDSAppDefinition(
        "universal-updater",
        "Universal-Updater",
        "bootstrap",
        "On-device homebrew catalogue/updater. Prefer it for packages that already have a maintained 3DS install recipe.",
        (
            "3ds/Universal-Updater.3dsx",
            "3ds/Universal-Updater/Universal-Updater.3dsx",
        ),
        "https://github.com/Universal-Team/Universal-Updater/releases",
        "manual_bootstrap",
        installed_title_may_exist_without_sd_marker=True,
        installed_title_ids=("0004000004391700",),
    ),
    ThreeDSAppDefinition(
        "godmode9",
        "GodMode9",
        "utility",
        "System and storage maintenance utility. Useful for recovery and console-owned dumps, but not required for normal ROM transfer.",
        ("luma/payloads/GodMode9.firm", "gm9"),
        "https://github.com/d0k3/GodMode9/releases",
        "guide_or_universal_updater",
    ),
    ThreeDSAppDefinition(
        "dsp-firmware",
        "DSP firmware dump",
        "system-data",
        "Console-specific DSP firmware used by some homebrew. It must be generated from the user's own console rather than downloaded by RommHeld.",
        ("3ds/dspfirm.cdc",),
        "https://3ds.hacks.guide/finalizing-setup.html",
        "console_generated",
    ),
    ThreeDSAppDefinition(
        "open-agb-firm",
        "open_agb_firm",
        "runtime",
        "Direct GBA runtime using the 3DS GBA hardware path.",
        ("luma/payloads/open_agb_firm.firm",),
        "https://github.com/profi200/open_agb_firm/releases",
        "universal_updater_or_manual",
        ("gba",),
    ),
    ThreeDSAppDefinition(
        "twilight",
        "TWiLight Menu++",
        "runtime",
        "Nintendo DS frontend used with nds-bootstrap on 3DS SD storage. Both the TWiLight assets and nds-bootstrap are required for the RommHeld NDS route, but those folders alone do not prove that the 3DS launcher title is installed.",
        ("_nds/TWiLightMenu", "_nds/nds-bootstrap"),
        "https://github.com/DS-Homebrew/TWiLightMenu/releases",
        "prefer_universal_updater",
        ("nds",),
        installed_title_may_exist_without_sd_marker=True,
        marker_policy="all",
        marker_confirms_launchable=False,
    ),
    ThreeDSAppDefinition(
        "retroarch",
        "RetroArch",
        "runtime",
        "Libretro frontend/core environment used for compatible emulated systems and RetroAchievements-capable routes. Data/core folders alone do not prove that a launchable frontend is installed.",
        ("RetroArch", "RetroArch/Cores", "retroarch/retroarch.cfg"),
        "https://www.retroarch.com/?page=platforms",
        "manual_bundle_or_updater",
        tuple(sorted(RETROARCH_TARGET_PLATFORM_SLUGS)),
        installed_title_may_exist_without_sd_marker=True,
        marker_confirms_launchable=False,
    ),
    ThreeDSAppDefinition(
        "red-viper",
        "Red Viper",
        "runtime",
        "Dedicated Virtual Boy emulator with 3DS-specific stereoscopic display support. ROM directories are not installation evidence because Red Viper can browse content from any SD location.",
        (
            "3ds/RedViper/RedViper.3dsx",
            "3ds/red-viper/red-viper.3dsx",
            "3ds/RedViper.3dsx",
        ),
        "https://github.com/skyfloogle/red-viper/releases",
        "universal_updater_or_manual",
        ("virtualboy",),
        installed_title_may_exist_without_sd_marker=True,
        installed_title_ids=("000400000FE7CB00",),
    ),
    ThreeDSAppDefinition(
        "daedalusx64",
        "DaedalusX64",
        "runtime",
        "Dedicated Nintendo 64 emulator. Its 3DS build documents ROM storage under /3ds/DaedalusX64/Roms/, but that content directory is not installation evidence.",
        ("3ds/DaedalusX64/DaedalusX64.3dsx", "3ds/DaedalusX64.3dsx"),
        "https://github.com/masterfeizz/DaedalusX64-3DS/releases",
        "manual_bundle_or_updater",
        ("n64",),
        installed_title_may_exist_without_sd_marker=True,
    ),
    ThreeDSAppDefinition(
        "checkpoint",
        "Checkpoint",
        "utility",
        "Save manager useful for backups before changing installed titles or experimenting with generated packages.",
        ("3ds/Checkpoint/Checkpoint.3dsx", "3ds/Checkpoint.3dsx"),
        "https://github.com/BernardoGiordano/Checkpoint/releases",
        "universal_updater_or_manual",
        installed_title_may_exist_without_sd_marker=True,
        installed_title_ids=("000400000BCFFF00",),
    ),
)


APP_BY_KEY = {app.key: app for app in THREE_DS_APPS}


# Compatibility-style runtime recommendations for broad readiness views. This
# is deliberately not the full set of selectable runtime targets. Per-title
# preference logic in three_ds_targets.py decides between alternatives such as
# Red Viper and RetroArch/Beetle VB for Virtual Boy.
RUNTIME_RECOMMENDATIONS: dict[str, tuple[str, ...]] = {
    "gba": ("open-agb-firm", "retroarch"),
    "nds": ("twilight",),
    "virtualboy": ("red-viper",),
    "n64": ("daedalusx64",),
}


def _case_insensitive_exists(root: Path, marker: str) -> bool:
    current = root
    for part in Path(marker).parts:
        if not current.is_dir():
            return False
        try:
            match = next(
                (entry for entry in current.iterdir() if entry.name.casefold() == part.casefold()),
                None,
            )
        except OSError:
            return False
        if match is None:
            return False
        current = match
    return current.exists()


def detect_three_ds_app(
    root: Path,
    definition: ThreeDSAppDefinition,
    *,
    visible_title_ids: frozenset[bytes] | None = None,
) -> ThreeDSAppStatus:
    root = root.expanduser()
    if not root.is_dir():
        return ThreeDSAppStatus(definition, False, None)

    matched = tuple(
        marker for marker in definition.markers if _case_insensitive_exists(root, marker)
    )
    marker_match = (
        len(matched) == len(definition.markers)
        if definition.marker_policy == "all"
        else bool(matched)
    )
    marker = "; ".join(matched) if marker_match and matched else None
    if marker_match and definition.marker_confirms_launchable:
        return ThreeDSAppStatus(definition, True, marker)

    if definition.installed_title_ids:
        title_ids = (
            mounted_sd_title_ids(root)
            if visible_title_ids is None
            else visible_title_ids
        )
        for raw_title_id in definition.installed_title_ids:
            normalized = raw_title_id.strip().upper()
            if bytes.fromhex(normalized) in title_ids:
                title_tree_marker = (
                    "Nintendo 3DS/<ID0>/<ID1>/title/"
                    f"{normalized[:8]}/{normalized[8:]}"
                )
                return ThreeDSAppStatus(
                    definition,
                    True,
                    title_tree_marker,
                    normalized,
                )

    return ThreeDSAppStatus(definition, False, marker)


def scan_three_ds_apps(root: Path) -> dict[str, ThreeDSAppStatus]:
    root = root.expanduser()
    visible_title_ids = mounted_sd_title_ids(root)
    return {
        app.key: detect_three_ds_app(
            root,
            app,
            visible_title_ids=visible_title_ids,
        )
        for app in THREE_DS_APPS
    }


def recommended_runtime_keys(platform_slugs: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for raw in platform_slugs:
        for key in RUNTIME_RECOMMENDATIONS.get(str(raw).lower(), ()):
            if key not in result:
                result.append(key)
    return tuple(result)


def readiness_component_keys(
    platform_slugs: Iterable[str] = (),
    *,
    needs_ftp: bool = True,
    needs_cia_install: bool = False,
) -> tuple[str, ...]:
    keys = ["luma", "homebrew-launcher", "universal-updater"]
    if needs_ftp:
        keys.append("ftpd")
    if needs_cia_install:
        keys.append("fbi")
    keys.extend(recommended_runtime_keys(platform_slugs))
    return tuple(dict.fromkeys(keys))
