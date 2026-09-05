from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .romm_remote import RomMRemoteGame
from .three_ds_ftp import ThreeDSFtpBackend, ThreeDSFtpSettings
from .three_ds_payload import (
    download_target_payload,
    planned_payload_filename,
    requires_payload_resolution,
    resolve_target_payload,
    temporary_payload_workspace,
)
from .three_ds_storage import ThreeDSMountedStorageBackend
from .three_ds_targets import default_destination


class ThreeDSFilesystemTransferWorker(QThread):
    """Target-aware 3DS filesystem transfer over mounted SD or ftpd.

    Raw-ROM targets resolve archives before destination comparison so compressed
    RomM/library files are never mistaken for launchable runtime payloads.
    """

    progress = Signal(int)
    status_changed = Signal(str)
    destination_resolved = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        transport: str,
        *,
        target_key: str,
        platform_slug: str,
        original_filename: str,
        source: Path | None = None,
        remote_game: RomMRemoteGame | None = None,
        romm_url: str = "",
        romm_token: str = "",
        storage_root: Path | None = None,
        ftp_settings: ThreeDSFtpSettings | None = None,
        overwrite: bool = False,
    ):
        super().__init__()
        if transport not in {"sd", "ftp"}:
            raise ValueError(f"Unknown Nintendo 3DS filesystem transport: {transport}")
        self.transport = transport
        self.target_key = target_key
        self.platform_slug = platform_slug
        self.original_filename = original_filename
        self.source = source
        self.remote_game = remote_game
        self.romm_url = romm_url
        self.romm_token = romm_token
        self.storage_root = storage_root
        self.ftp_settings = ftp_settings
        self.overwrite = overwrite
        self.cancel_event = threading.Event()
        self.backend: ThreeDSFtpBackend | ThreeDSMountedStorageBackend | None = None
        self._payload_size = 0
        self._download_phase = False

    def cancel(self) -> None:
        self.cancel_event.set()

    def _check_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise InterruptedError

    def _download_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.progress.emit(max(0, min(45, int(done * 45 / total))))
        else:
            self.progress.emit(0)

    def _upload_progress(self, done: int) -> None:
        total = self._payload_size
        if total <= 0:
            return
        if self._download_phase:
            value = 50 + int(done * 50 / total)
        else:
            value = int(done * 100 / total)
        self.progress.emit(max(0, min(100, value)))

    def _open_backend(self):
        if self.transport == "sd":
            if self.storage_root is None:
                raise ValueError("No validated Nintendo 3DS SD card is mounted.")
            self.backend = ThreeDSMountedStorageBackend(self.storage_root)
            return self.backend

        if self.ftp_settings is None:
            raise ValueError("Nintendo 3DS ftpd is not configured.")
        ftp = ThreeDSFtpBackend(self.ftp_settings)
        self.backend = ftp
        self.status_changed.emit("Connecting to Nintendo 3DS ftpd…")
        ftp.connect()
        return ftp

    def _remote_payload(
        self,
        workspace: Path,
    ) -> tuple[Path | None, int, str]:
        assert self.remote_game is not None
        if not self.romm_url.strip() or not self.romm_token.strip():
            raise ValueError("RomM server credentials are not configured.")

        needs_resolution = requires_payload_resolution(
            self.target_key,
            self.platform_slug,
            self.original_filename,
        )
        planned_name = planned_payload_filename(
            self.target_key,
            self.platform_slug,
            self.original_filename,
        )

        if not needs_resolution and planned_name:
            expected_size = int(self.remote_game.size or 0)
            destination = default_destination(
                self.target_key,
                self.platform_slug,
                planned_name,
            )
            if expected_size > 0:
                return None, expected_size, destination

        self._download_phase = True
        self.status_changed.emit(f"Downloading {self.remote_game.name} from RomM…")
        payload = download_target_payload(
            self.romm_url,
            self.romm_token,
            self.remote_game,
            self.target_key,
            self.platform_slug,
            workspace,
            cancel_event=self.cancel_event,
            progress=self._download_progress,
        )
        self._check_cancelled()
        expected_size = payload.stat().st_size
        destination = default_destination(
            self.target_key,
            self.platform_slug,
            payload.name,
        )
        return payload, expected_size, destination

    def _local_payload(self, workspace: Path) -> tuple[Path, int, str]:
        if self.source is None or not self.source.is_file():
            raise FileNotFoundError(
                "The selected local file is no longer available. Refresh the Library and retry."
            )
        payload = resolve_target_payload(
            self.source,
            self.target_key,
            self.platform_slug,
            workspace,
        )
        expected_size = payload.stat().st_size
        destination = default_destination(
            self.target_key,
            self.platform_slug,
            payload.name,
        )
        return payload, expected_size, destination

    def _download_after_precheck(self, workspace: Path) -> Path:
        assert self.remote_game is not None
        self._download_phase = True
        self.status_changed.emit(f"Downloading {self.remote_game.name} from RomM…")
        payload = download_target_payload(
            self.romm_url,
            self.romm_token,
            self.remote_game,
            self.target_key,
            self.platform_slug,
            workspace,
            cancel_event=self.cancel_event,
            progress=self._download_progress,
        )
        self._check_cancelled()
        return payload

    def run(self) -> None:
        try:
            with temporary_payload_workspace() as workspace_name:
                workspace = Path(workspace_name)
                if self.remote_game is not None:
                    payload, expected_size, destination = self._remote_payload(workspace)
                    display_name = self.remote_game.name
                else:
                    payload, expected_size, destination = self._local_payload(workspace)
                    display_name = payload.name

                self._payload_size = expected_size
                self.destination_resolved.emit(destination)
                self._check_cancelled()

                route_name = (
                    "the mounted Nintendo 3DS SD card"
                    if self.transport == "sd"
                    else "the Nintendo 3DS"
                )
                self.status_changed.emit(f"Checking {display_name} on {route_name}…")
                backend = self._open_backend()
                current_size = backend.remote_size(destination)
                if current_size == expected_size:
                    self.progress.emit(100)
                    self.completed.emit("skipped")
                    return
                if current_size is not None and not self.overwrite:
                    self.completed.emit("different")
                    return
                self._check_cancelled()

                if payload is None:
                    payload = self._download_after_precheck(workspace)
                    actual_size = payload.stat().st_size
                    if actual_size != expected_size:
                        raise IOError(
                            f"RomM download size mismatch for {display_name}: "
                            f"expected {expected_size} bytes, got {actual_size}."
                        )
                    resolved_destination = default_destination(
                        self.target_key,
                        self.platform_slug,
                        payload.name,
                    )
                    if resolved_destination != destination:
                        raise ValueError(
                            "The resolved Nintendo 3DS destination changed after download; "
                            "refusing to transfer an ambiguous payload."
                        )

                self._check_cancelled()
                if self.transport == "sd":
                    self.status_changed.emit(
                        f"Copying {payload.name} to the mounted Nintendo 3DS SD card…"
                    )
                else:
                    self.status_changed.emit(
                        f"Uploading {payload.name} to a verified staging file on the Nintendo 3DS…"
                    )
                result, _ = backend.upload(
                    payload,
                    destination,
                    overwrite=self.overwrite,
                    cancel_event=self.cancel_event,
                    progress=self._upload_progress,
                )
                if result in {"copied", "resumed", "skipped"}:
                    self.progress.emit(100)
                self.completed.emit(result)
        except InterruptedError:
            self.completed.emit("cancelled")
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if isinstance(self.backend, ThreeDSFtpBackend):
                self.backend.close()
            self.backend = None


__all__ = ["ThreeDSFilesystemTransferWorker"]
