from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtCore import QStorageInfo

APP_NAME = "RommHeld"


def _qt_location(location: QStandardPaths.StandardLocation, fallback: Path) -> Path:
    value = QStandardPaths.writableLocation(location)
    return Path(value) if value else fallback


def config_dir() -> Path:
    return _qt_location(
        QStandardPaths.StandardLocation.AppConfigLocation,
        Path.home() / ".config" / "rommheld",
    )


def cache_dir() -> Path:
    return _qt_location(
        QStandardPaths.StandardLocation.CacheLocation,
        Path.home() / ".cache" / "rommheld",
    )


def config_path() -> Path:
    return config_dir() / "config.json"


def temp_dir() -> Path:
    value = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation)
    return Path(value) / APP_NAME if value else cache_dir() / "tmp"


def writable_volumes() -> list[Path]:
    volumes: list[Path] = []
    for storage in QStorageInfo.mountedVolumes():
        if not storage.isValid() or not storage.isReady() or storage.isReadOnly():
            continue
        root = Path(storage.rootPath())
        if root.exists():
            volumes.append(root)
    return sorted(set(volumes), key=lambda p: str(p).lower())


def volume_info(path: Path) -> dict[str, object]:
    storage = QStorageInfo(str(path))
    return {
        "root": Path(storage.rootPath()),
        "name": storage.name(),
        "display_name": storage.displayName(),
        "filesystem": storage.fileSystemType().data().decode(errors="replace")
        if storage.fileSystemType()
        else "",
        "is_ready": storage.isReady(),
        "is_read_only": storage.isReadOnly(),
        "bytes_total": int(storage.bytesTotal()),
        "bytes_free": int(storage.bytesFree()),
    }


def process_id() -> int:
    return os.getpid()
