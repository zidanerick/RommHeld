from __future__ import annotations

import re
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .mappings import ROMM_TO_RETROFLOW
from .models import Game
from .transfers import copy_file_chunked


def human_size(value: int) -> str:
    n = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{value} B"


def sanitize_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", " ", name).strip().rstrip(".")
    return name or "Game"


def adrenaline_game_folder_name(game: Game) -> str:
    """Return the PSP/GAME folder name for an Adrenaline EBOOT.PBP deployment."""
    if game.path.name.lower() == "eboot.pbp":
        return sanitize_name(game.path.parent.name)
    return sanitize_name(game.name)


def destination_for_game(
    vita: Path,
    game: Game,
    mappings: dict[str, str | None],
) -> tuple[str, Path, str]:
    key = game.source_platform.lower()
    suffix = game.path.suffix.lower()

    if key == "psp":
        if suffix in {".iso", ".cso"}:
            return "PSP / Adrenaline ISO", vita / "pspemu" / "ISO", "file"
        if suffix == ".pbp":
            return (
                "PSP / Adrenaline GAME",
                vita / "pspemu" / "PSP" / "GAME",
                "game-folder",
            )
        return (
            "PSP requires ISO/CSO or EBOOT.PBP",
            vita / "pspemu",
            "unknown",
        )

    if key in {"psx", "ps1", "playstation"}:
        if suffix == ".pbp":
            return (
                "PS1 / Adrenaline GAME",
                vita / "pspemu" / "PSP" / "GAME",
                "game-folder",
            )
        return (
            "PS1 requires an EBOOT.PBP for Adrenaline",
            vita / "pspemu" / "PSP" / "GAME",
            "unknown",
        )

    if key in {"nds", "ds", "nintendo-ds"}:
        if suffix == ".nds":
            return (
                "Nintendo DS / DSVita",
                vita / "data" / "dsvita",
                "file",
            )
        return (
            "DSVita requires an .nds ROM",
            vita / "data" / "dsvita",
            "unknown",
        )

    if key == "vita":
        if suffix == ".vpk":
            return (
                "PS Vita VPK staging",
                vita,
                "staging",
            )
        return (
            "PS Vita deployment requires a VPK",
            vita,
            "unknown",
        )

    if key in mappings:
        folder = mappings[key]
    else:
        folder = ROMM_TO_RETROFLOW.get(key)
    if folder:
        return (
            f"RetroFlow / {folder}",
            vita / "data" / "RetroFlow" / "ROMS" / folder,
            "file",
        )
    return (
        "Needs destination review",
        vita / "data" / "RetroFlow" / "ROMS",
        "unknown",
    )


def destination_target(
    vita: Path,
    game: Game,
    mappings: dict[str, str | None],
) -> tuple[str, Path, str]:
    label, destination, mode = destination_for_game(vita, game, mappings)
    if mode == "game-folder":
        return (
            label,
            destination / adrenaline_game_folder_name(game) / "EBOOT.PBP",
            mode,
        )
    return label, destination / game.path.name, mode


def game_status(
    vita: Path | None,
    game: Game,
    mappings: dict[str, str | None],
) -> tuple[str, str]:
    if vita is None:
        return "UNKNOWN", "Vita not connected"
    label, target, mode = destination_target(vita, game, mappings)
    if mode == "unknown":
        return "UNKNOWN", "No safe destination mapping"
    try:
        if not target.exists():
            return "NEW", f"→ {label}"
        if target.is_file() and target.stat().st_size == game.size:
            if mode == "staging":
                return "STAGED", "VPK staged; install it with VitaShell"
            return "INSTALLED", "Same-size file already present"
        return "DIFFERENT", "Destination exists with different size"
    except OSError as exc:
        return "UNKNOWN", str(exc)


class CopyWorker(QThread):
    progress = Signal(int, str, str)
    finished_ok = Signal(int, int, int)
    failed = Signal(str)

    def __init__(self, jobs):
        super().__init__()
        self.jobs = jobs
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        copied = skipped = cancelled = 0
        try:
            total = sum(game.size for game, *_ in self.jobs) or 1
            completed = 0
            for game, destination, mode, label in self.jobs:
                if self.cancel_event.is_set():
                    cancelled += 1
                    break

                if mode == "game-folder":
                    target = (
                        destination
                        / adrenaline_game_folder_name(game)
                        / "EBOOT.PBP"
                    )
                else:
                    target = destination / game.path.name

                if (
                    target.exists()
                    and target.is_file()
                    and target.stat().st_size == game.size
                ):
                    skipped += 1
                    completed += game.size
                    detail = "Already staged" if mode == "staging" else "Already present"
                    self.progress.emit(
                        int(completed * 100 / total), game.name, detail
                    )
                    continue

                def report(done: int) -> None:
                    self.progress.emit(
                        int((completed + done) * 100 / total),
                        game.name,
                        f"{human_size(done)} / {human_size(game.size)} → {label}",
                    )

                ok = copy_file_chunked(
                    game.path,
                    target,
                    self.cancel_event,
                    progress=report,
                )
                if not ok:
                    cancelled += 1
                    break
                if target.stat().st_size != game.size:
                    raise IOError(f"Size verification failed for {game.name}")
                copied += 1
                completed += game.size

            self.finished_ok.emit(copied, skipped, cancelled)
        except Exception as exc:
            self.failed.emit(str(exc))


__all__ = [
    "CopyWorker",
    "adrenaline_game_folder_name",
    "destination_for_game",
    "destination_target",
    "game_status",
    "human_size",
    "sanitize_name",
]
