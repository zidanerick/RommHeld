from __future__ import annotations

import re
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

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


def destination_for_game(
    vita: Path,
    game: Game,
    mappings: dict[str, str | None],
) -> tuple[str, Path, str]:
    key = game.source_platform.lower()
    if key == "psp":
        return "PSP / Adrenaline ISO", vita / "pspemu" / "ISO", "file"
    if key in {"psx", "ps1", "playstation"}:
        return (
            "PS1 / Adrenaline GAME",
            vita / "pspemu" / "PSP" / "GAME",
            "game-folder",
        )
    if key == "vita":
        return (
            "PS Vita VPK staging",
            vita / "data" / "RetroFlow" / "ROMS",
            "staging",
        )
    folder = mappings.get(key)
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
        return label, destination / sanitize_name(game.name) / "EBOOT.PBP", mode
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
            return "INSTALLED", "Same-size file already present"
        return "DIFFERENT", "Destination exists with different size"
    except OSError as exc:
        return "UNKNOWN", str(exc)


class CopyWorker(QThread):
    progress = Signal(int, str, str)
    finished_ok = Signal(int, int, int)
    failed = Signal(str)

    def __init__(self, jobs: list[tuple[Game, Path, str, str]]):
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

                target = (
                    destination / sanitize_name(game.name) / "EBOOT.PBP"
                    if mode == "game-folder"
                    else destination / game.path.name
                )
                if (
                    target.exists()
                    and target.is_file()
                    and target.stat().st_size == game.size
                ):
                    skipped += 1
                    completed += game.size
                    self.progress.emit(
                        int(completed * 100 / total), game.name, "Already present"
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
    "destination_for_game",
    "destination_target",
    "game_status",
    "human_size",
    "sanitize_name",
]
