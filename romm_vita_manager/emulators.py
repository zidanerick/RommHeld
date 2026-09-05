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
        ("retroarch", "retroarch-data"),
        "Preferred route for supported RetroAchievements systems",
        "RetroArch's Vita build needs both the VPK and data package.",
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
        ("flycast",),
        (),
        (),
        "Separate from the main RetroArch plan",
        "No automated package is configured yet.",
    ),
    EmulatorDefinition(
        "scummvm",
        "ScummVM",
        "Adventure-game engine and launcher.",
        ("scummvm",),
        (),
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
        ("fake-08", "fake08"),
        (),
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
