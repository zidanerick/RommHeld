from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .three_ds_apps import APP_BY_KEY, ThreeDSAppStatus, detect_three_ds_app


@dataclass(frozen=True)
class ReadinessRequirement:
    app_key: str
    importance: str
    reason: str

    def __post_init__(self) -> None:
        if self.importance not in {"required", "recommended", "optional"}:
            raise ValueError(f"Unknown readiness importance: {self.importance}")
        if self.app_key not in APP_BY_KEY:
            raise KeyError(f"Unknown 3DS readiness app: {self.app_key}")


@dataclass(frozen=True)
class ReadinessItem:
    requirement: ReadinessRequirement
    status: ThreeDSAppStatus

    @property
    def required(self) -> bool:
        return self.requirement.importance == "required"

    @property
    def needs_console_confirmation(self) -> bool:
        return (
            self.required
            and not self.status.detected
            and self.status.definition.installed_title_may_exist_without_sd_marker
        )

    @property
    def definitely_missing(self) -> bool:
        return (
            self.required
            and not self.status.detected
            and not self.status.definition.installed_title_may_exist_without_sd_marker
        )


@dataclass(frozen=True)
class ThreeDSReadinessReport:
    root: Path
    items: tuple[ReadinessItem, ...]

    @property
    def missing_required(self) -> tuple[ReadinessItem, ...]:
        return tuple(item for item in self.items if item.definitely_missing)

    @property
    def unconfirmed_required(self) -> tuple[ReadinessItem, ...]:
        return tuple(item for item in self.items if item.needs_console_confirmation)

    @property
    def state(self) -> str:
        if self.missing_required:
            return "missing_required"
        if self.unconfirmed_required:
            return "needs_confirmation"
        return "ready"


TARGET_RUNTIME_APPS = {
    "open_agb_firm": "open-agb-firm",
    "twilight": "twilight",
    "red_viper": "red-viper",
    "daedalusx64": "daedalusx64",
    "retroarch": "retroarch",
}


@dataclass(frozen=True)
class TargetRuntimePreflight:
    target_key: str
    app_key: str
    app_name: str
    state: str
    note: str


def evaluate_target_runtime(
    root: Path,
    target_key: str,
) -> TargetRuntimePreflight | None:
    """Summarize SD-visible readiness for the runtime required by a target.

    This is deliberately non-blocking. Some runtimes can be installed as CIA
    titles without leaving a reliable SD marker, so absence can mean either a
    definite missing runtime or a console-confirmation state.
    """
    normalized_target = str(target_key).strip()
    app_key = TARGET_RUNTIME_APPS.get(normalized_target)
    if app_key is None:
        return None

    definition = APP_BY_KEY[app_key]
    status = detect_three_ds_app(root.expanduser(), definition)
    if status.detected:
        return TargetRuntimePreflight(
            normalized_target,
            app_key,
            definition.name,
            "detected",
            f"{definition.name} was detected from the mounted 3DS SD card.",
        )
    if definition.installed_title_may_exist_without_sd_marker:
        return TargetRuntimePreflight(
            normalized_target,
            app_key,
            definition.name,
            "confirm_on_console",
            (
                f"{definition.name} was not detected from SD files. It may be installed "
                "as a CIA title, so confirm it on the console before expecting this ROM to launch."
            ),
        )
    return TargetRuntimePreflight(
        normalized_target,
        app_key,
        definition.name,
        "missing",
        (
            f"{definition.name} was not detected on the mounted 3DS SD card. The ROM can still "
            "be copied now, but this route will not be launchable until that runtime is installed."
        ),
    )


def _append_requirement(
    result: list[ReadinessRequirement],
    app_key: str,
    importance: str,
    reason: str,
) -> None:
    existing_index = next(
        (index for index, item in enumerate(result) if item.app_key == app_key),
        None,
    )
    requirement = ReadinessRequirement(app_key, importance, reason)
    if existing_index is None:
        result.append(requirement)
        return

    existing = result[existing_index]
    rank = {"optional": 0, "recommended": 1, "required": 2}
    if rank[importance] > rank[existing.importance]:
        result[existing_index] = requirement


def build_readiness_requirements(
    target_keys: Iterable[str] = (),
    *,
    needs_ftp: bool = True,
    needs_cia_install: bool = False,
    include_utilities: bool = True,
) -> tuple[ReadinessRequirement, ...]:
    result: list[ReadinessRequirement] = []

    _append_requirement(
        result,
        "luma",
        "required",
        "RommHeld's supported 3DS homebrew workflows assume a working Luma3DS custom-firmware environment.",
    )
    _append_requirement(
        result,
        "universal-updater",
        "recommended",
        "Use Universal-Updater for maintained on-device installation and updates instead of making RommHeld a general homebrew store.",
    )

    if needs_ftp:
        _append_requirement(
            result,
            "homebrew-launcher",
            "recommended",
            "Homebrew Launcher is needed when ftpd is used as a 3DSX application, but an installed ftpd CIA can provide the FTP server without it.",
        )
        _append_requirement(
            result,
            "ftpd",
            "required",
            "RommHeld uses ftpd-compatible FTP access for live filesystem transfers to the 3DS.",
        )

    if needs_cia_install:
        _append_requirement(
            result,
            "fbi",
            "required",
            "FBI is required for RommHeld's Remote Install workflow and for installing staged CIA packages on-console.",
        )
        _append_requirement(
            result,
            "checkpoint",
            "recommended",
            "Checkpoint is useful for backing up save data before replacing or experimenting with installed titles.",
        )

    for target_key in target_keys:
        runtime_key = TARGET_RUNTIME_APPS.get(str(target_key))
        if runtime_key is None:
            continue
        _append_requirement(
            result,
            runtime_key,
            "required",
            f"The selected {target_key} deployment route requires this runtime.",
        )
        if target_key in {"red_viper", "daedalusx64"}:
            _append_requirement(
                result,
                "dsp-firmware",
                "recommended",
                (
                    "Red Viper documents DSP firmware as a troubleshooting prerequisite on modded 3DS systems."
                    if target_key == "red_viper"
                    else "DaedalusX64's upstream 3DS release recommends a dumped DSP firmware when game launch freezes."
                ),
            )

    if include_utilities:
        _append_requirement(
            result,
            "godmode9",
            "recommended",
            "GodMode9 is useful for console-owned dumps, recovery, and storage maintenance, but is not required for normal RommHeld transfers.",
        )
        _append_requirement(
            result,
            "checkpoint",
            "recommended",
            "Checkpoint provides save backups and recovery without being required for normal transfers.",
        )

    return tuple(result)


def evaluate_readiness(
    root: Path,
    target_keys: Iterable[str] = (),
    *,
    needs_ftp: bool = True,
    needs_cia_install: bool = False,
    include_utilities: bool = True,
) -> ThreeDSReadinessReport:
    requirements = build_readiness_requirements(
        target_keys,
        needs_ftp=needs_ftp,
        needs_cia_install=needs_cia_install,
        include_utilities=include_utilities,
    )
    items = tuple(
        ReadinessItem(
            requirement,
            detect_three_ds_app(root, APP_BY_KEY[requirement.app_key]),
        )
        for requirement in requirements
    )
    return ThreeDSReadinessReport(root.expanduser(), items)
