from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EmulatorDefinition:
    key: str
    name: str
    description: str
    app_patterns: tuple[str, ...]
    detection_paths: tuple[str, ...]
    package_keys: tuple[str, ...] = ()
    achievement_role: str = "Not applicable"
    install_note: str = ""


EMULATORS = (
    EmulatorDefinition(
        "retroflow",
        "RetroFlow",
        "Frontend/launcher for the Vita library.",
        ("retroflow",),
        ("app/RETROFLOW",),
        ("retroflow",),
        "Frontend only; not an achievement emulator",
        "Installing RetroFlow is optional when it is already present.",
    ),
    EmulatorDefinition(
        "adrenaline",
        "Adrenaline",
        "PSP and PS1 environment.",
        ("pspemucfw", "adrenaline"),
        ("app/PSPEMUCFW",),
        ("adrenaline",),
        "Separate from RetroArch achievements",
        "Use VitaShell for a fresh VPK installation. Existing installations may need the upstream update procedure.",
    ),
    EmulatorDefinition(
        "retroarch",
        "RetroArch",
        "Retro emulator platform and libretro cores.",
        ("retrovita", "retroarch"),
        ("app/RETROVITA", "app/RETROARCH"),
        ("retroarch",),
        "Preferred route for supported RetroAchievements systems",
        "Install the RetroArch VPK with VitaShell, then prepare the separate RetroArch data payload below.",
    ),
    EmulatorDefinition(
        "retroarch-data",
        "RetroArch data",
        "Required assets/data companion package for the Vita RetroArch build.",
        (),
        ("data/retroarch",),
        ("retroarch-data",),
        "Required companion data for RetroArch",
        "Download and inspect the data archive. Its contents belong under ux0:/data/retroarch/. RommHeld does not auto-extract 7z archives until a traversal-safe extraction path is implemented.",
    ),
    EmulatorDefinition(
        "daedalusx64",
        "DaedalusX64",
        "Vita-native Nintendo 64 emulator used by RetroFlow setups.",
        ("dedalox64", "daedalusx64", "daedalus"),
        ("app/DEDALOX64",),
        ("daedalusx64",),
        "Do not assume achievement compatibility",
        "Keep this separate from an achievement-first RetroArch configuration.",
    ),
    EmulatorDefinition(
        "flycast",
        "Flycast",
        "Dreamcast emulator.",
        ("flycastdc", "flycast"),
        ("app/FLYCASTDC",),
        (),
        "Separate from the main RetroArch plan",
        "No automated package is configured yet.",
    ),
    EmulatorDefinition(
        "scummvm",
        "ScummVM",
        "Adventure-game engine and launcher.",
        ("vscu00001", "scummvm"),
        ("app/VSCU00001",),
        (),
        "Not a RetroArch core route",
        "No automated package is configured yet.",
    ),
    EmulatorDefinition(
        "dsvita",
        "DSVita",
        "Nintendo DS emulator.",
        ("dsvita000", "dsvita"),
        ("app/DSVITA000",),
        ("dsvita",),
        "Not a RetroAchievements-first route",
        "Requires libshacccg.suprx and kubridge >= 0.3.1; ROMs use ux0:/data/dsvita/.",
    ),
    EmulatorDefinition(
        "fake-08",
        "FAKE-08",
        "Pico-8 fantasy-console emulator for Vita.",
        ("fake00008", "fake-08", "fake08"),
        ("app/FAKE00008",),
        (),
        "Not a RetroAchievements-first route",
        "No automated package is configured yet.",
    ),
)


def _app_dirs(vita: Path) -> list[str]:
    app = vita / "app"
    if not app.is_dir():
        return []
    try:
        return [p.name.lower() for p in app.iterdir() if p.is_dir()]
    except OSError:
        return []


def detect_emulators(vita: Path) -> dict[str, bool]:
    names = _app_dirs(vita)
    result: dict[str, bool] = {}
    for emulator in EMULATORS:
        app_match = any(
            pattern in name
            for name in names
            for pattern in emulator.app_patterns
        )
        path_match = any((vita / rel).exists() for rel in emulator.detection_paths)
        result[emulator.key] = app_match or path_match
    return result
