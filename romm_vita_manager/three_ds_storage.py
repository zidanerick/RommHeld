from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from .file_transfer import required_transfer_space, transfer_file
from .local_storage import resolve_destination, resolve_storage_root, storage_summary
from .storage_validation import validate_3ds_sd


def configured_3ds_storage_root(config: dict) -> Path | None:
    """Return the configured mounted 3DS SD root when it is still valid."""
    raw = str(
        config.get("devices", {}).get("3ds", {}).get("storage_root", "")
    ).strip()
    # Read compatibility for the brief integration-branch top-level variant.
    if not raw:
        raw = str(config.get("three_ds_sd_root", "")).strip()
    if not raw:
        return None
    try:
        root = resolve_storage_root(raw)
        validation = validate_3ds_sd(root)
    except (OSError, ValueError):
        return None
    if validation.confidence not in {"medium", "high"}:
        return None
    return root


def with_3ds_storage_root(config: dict, root: str | Path) -> dict:
    """Return config updated with a validated 3DS mounted-storage root."""
    resolved = resolve_storage_root(root)
    validation = validate_3ds_sd(resolved)
    if validation.confidence not in {"medium", "high"}:
        raise ValueError(
            "Selected directory does not have enough Nintendo 3DS SD-card markers. "
            "Choose the card root that contains files such as boot.firm, boot.3dsx, luma/, or gm9/."
        )
    updated = dict(config)
    devices = dict(updated.get("devices", {}))
    three_ds = dict(devices.get("3ds", {}))
    three_ds["storage_root"] = str(resolved)
    devices["3ds"] = three_ds
    updated["devices"] = devices
    updated.pop("three_ds_sd_root", None)
    return updated


class ThreeDSMountedStorageBackend:
    """Safe filesystem transport for a 3DS SD/microSD mounted on the desktop."""

    def __init__(self, root: str | Path):
        self.root = resolve_storage_root(root)
        validation = validate_3ds_sd(self.root)
        if validation.confidence not in {"medium", "high"}:
            raise ValueError(
                "Mounted storage is not a sufficiently validated Nintendo 3DS SD-card root."
            )
        self.validation = validation

    def destination_path(self, destination: str) -> Path:
        return resolve_destination(self.root, destination)

    def remote_size(self, destination: str) -> int | None:
        target = self.destination_path(destination)
        try:
            return target.stat().st_size if target.is_file() else None
        except OSError:
            return None

    def available_space(self) -> int | None:
        _total, free = storage_summary(self.root)
        return free

    def upload(
        self,
        source: Path,
        destination: str,
        *,
        overwrite: bool = False,
        cancel_event: threading.Event | None = None,
        progress: Callable[[int], None] | None = None,
    ) -> tuple[str, Path]:
        source = source.expanduser()
        if not source.is_file():
            raise FileNotFoundError(f"Source file does not exist: {source}")
        target = self.destination_path(destination)
        source_size = source.stat().st_size
        needed = required_transfer_space(source_size, target, overwrite=overwrite)
        free = self.available_space()
        if free is not None and needed > free:
            raise OSError(
                "Not enough free space on the mounted Nintendo 3DS SD card for the safe staged transfer. "
                f"{needed} bytes are required, but only {free} bytes are available."
            )
        event = cancel_event or threading.Event()
        result, _ = transfer_file(
            source,
            target,
            event,
            progress=progress,
            overwrite=overwrite,
        )
        return result, target


__all__ = [
    "ThreeDSMountedStorageBackend",
    "configured_3ds_storage_root",
    "with_3ds_storage_root",
]
