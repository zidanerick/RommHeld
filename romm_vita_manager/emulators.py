from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EmulatorDefinition:
    key: str
    name: str
    description: str
    detection_paths: tuple[str, ...]
    achievement_role: str = "Not applicable"


EMULATORS = (
    EmulatorDefinition(
        "retroflow", "RetroFlow", "Frontend/launcher for the Vita library.",
        ("app/RETROFLOW",),
    ),
    EmulatorDefinition(
        "adrenaline", "Adrenaline", "PSP and PS1 environment.",
        ("app/PSPEMUCFW",),
        "Separate from RetroArch achievements",
    ),
    EmulatorDefinition(
        "retroarch", "RetroArch", "Retro emulator platform and libretro cores.",
        (),
        "Preferred route for supported RetroAchievements systems",
    ),
    EmulatorDefinition(
        "daedalusx64", "DaedalusX64", "Nintendo 64 emulator used by RetroFlow setups.",
        (),
        "Do not assume achievement compatibility",
    ),
    EmulatorDefinition(
        "flycast", "Flycast", "Dreamcast emulator.",
        (),
        "Separate from the main RetroArch plan",
    ),
    EmulatorDefinition(
        "scummvm", "ScummVM", "Adventure-game engine and launcher.",
        (),
    ),
    EmulatorDefinition(
        "dsvita", "DSVita", "Nintendo DS emulator.",
        ("data/dsvita",),
    ),
)


def detect_emulators(vita: Path) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for emulator in EMULATORS:
        if emulator.detection_paths:
            result[emulator.key] = any((vita / rel).exists() for rel in emulator.detection_paths)
        else:
            result[emulator.key] = False
    return result
