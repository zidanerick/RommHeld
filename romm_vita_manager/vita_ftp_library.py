from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .models import Game
from .vita_ftp import VitaFtpBackend, VitaFtpSettings
from .vita_library_support import destination_target, human_size


def ftp_destination_target(
    game: Game,
    mappings: dict[str, str | None],
) -> tuple[str, str, str]:
    """Return the ux0 VitaShell FTP destination for an existing Vita mapping."""
    label, local_target, mode = destination_target(Path("/"), game, mappings)
    if mode == "unknown":
        return label, "", mode
    relative = local_target.relative_to(Path("/")).as_posix()
    return label, f"ux0:/{relative}", mode


class VitaFtpCopyWorker(QThread):
    """Copy a Vita library batch through one VitaShell FTP session."""

    progress = Signal(int, str, str)
    finished_ok = Signal(int, int, int)
    failed = Signal(str)

    def __init__(self, settings: VitaFtpSettings, jobs):
        super().__init__()
        self.settings = settings
        self.jobs = jobs
        self.cancel_event = threading.Event()
        self.backend: VitaFtpBackend | None = None

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        copied = skipped = cancelled = 0
        try:
            total = sum(game.size for game, *_ in self.jobs) or 1
            completed = 0
            self.backend = VitaFtpBackend(self.settings)
            self.backend.connect()

            for game, destination, label in self.jobs:
                if self.cancel_event.is_set():
                    cancelled += 1
                    break

                def report(done: int) -> None:
                    self.progress.emit(
                        int((completed + done) * 100 / total),
                        game.name,
                        f"{human_size(done)} / {human_size(game.size)} → {label} via FTP",
                    )

                result, _ = self.backend.upload(
                    game.path,
                    destination,
                    overwrite=True,
                    cancel_event=self.cancel_event,
                    progress=report,
                )
                if result == "cancelled":
                    cancelled += 1
                    break
                if result == "skipped":
                    skipped += 1
                    detail = "Already present"
                elif result == "copied":
                    copied += 1
                    detail = "Copied and verified"
                else:
                    raise RuntimeError(
                        f"Unexpected Vita FTP transfer result for {game.name}: {result}"
                    )
                completed += game.size
                self.progress.emit(
                    int(completed * 100 / total),
                    game.name,
                    detail,
                )

            self.finished_ok.emit(copied, skipped, cancelled)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if self.backend is not None:
                self.backend.close()


__all__ = ["VitaFtpCopyWorker", "ftp_destination_target"]
