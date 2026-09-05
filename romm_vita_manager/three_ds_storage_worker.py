from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .romm_remote import RomMRemoteGame, download_rom
from .three_ds_storage import ThreeDSMountedStorageBackend


class ThreeDSMountedTransferWorker(QThread):
    """Transfer a local or RomM-backed game to a validated mounted 3DS SD root."""

    progress = Signal(int)
    status_changed = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        root: Path,
        source: Path | None,
        destination: str,
        *,
        remote_game: RomMRemoteGame | None = None,
        romm_url: str = "",
        romm_token: str = "",
        overwrite: bool = False,
    ):
        super().__init__()
        self.root = root
        self.source = source
        self.destination = destination
        self.remote_game = remote_game
        self.romm_url = romm_url
        self.romm_token = romm_token
        self.overwrite = overwrite
        self.cancel_event = threading.Event()
        self._temporary_path: Path | None = None

    def cancel(self) -> None:
        self.cancel_event.set()

    def _resolve_source(self) -> Path:
        if self.remote_game is None:
            if self.source is None or not self.source.is_file():
                raise FileNotFoundError(f"Source file does not exist: {self.source}")
            return self.source
        if not self.romm_url.strip() or not self.romm_token.strip():
            raise ValueError("RomM server credentials are not configured.")
        handle = tempfile.NamedTemporaryFile(
            prefix="rommheld-3ds-sd-",
            suffix=Path(self.remote_game.filename).suffix,
            delete=False,
        )
        handle.close()
        self._temporary_path = Path(handle.name)
        self.status_changed.emit(f"Downloading {self.remote_game.name} from RomM…")
        return download_rom(
            self.romm_url,
            self.romm_token,
            self.remote_game,
            self._temporary_path,
            cancel_event=self.cancel_event,
            progress=lambda done, _total: self.progress.emit(done),
        )

    def run(self) -> None:
        try:
            if self.cancel_event.is_set():
                self.completed.emit("cancelled")
                return

            backend = ThreeDSMountedStorageBackend(self.root)
            source: Path | None = None
            if self.remote_game is not None:
                expected_size = int(self.remote_game.size)
                name = self.remote_game.name
                if expected_size <= 0:
                    source = self._resolve_source()
                    expected_size = source.stat().st_size
            else:
                source = self._resolve_source()
                expected_size = source.stat().st_size
                name = source.name

            self.status_changed.emit(
                f"Checking {name} on the mounted Nintendo 3DS SD card…"
            )
            current_size = backend.remote_size(self.destination)
            if current_size == expected_size:
                self.completed.emit("skipped")
                return
            if current_size is not None and not self.overwrite:
                self.completed.emit("different")
                return
            if self.cancel_event.is_set():
                self.completed.emit("cancelled")
                return

            if source is None:
                source = self._resolve_source()
                if source.stat().st_size != expected_size:
                    raise IOError(
                        f"RomM download size mismatch for {name}: expected {expected_size} bytes, "
                        f"got {source.stat().st_size}."
                    )

            self.status_changed.emit(f"Copying {name} to the mounted Nintendo 3DS SD card…")
            result, _ = backend.upload(
                source,
                self.destination,
                overwrite=self.overwrite,
                cancel_event=self.cancel_event,
                progress=self.progress.emit,
            )
            self.completed.emit(result)
        except InterruptedError:
            self.completed.emit("cancelled")
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if self._temporary_path is not None:
                try:
                    self._temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass


__all__ = ["ThreeDSMountedTransferWorker"]
