from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QStandardPaths, QStorageInfo, QUrl
from PySide6.QtGui import QDesktopServices

APP_NAME = "RommHeld"


def _ensure_application_identity() -> None:
    """Keep app-scoped Qt paths stable before and after QApplication exists.

    Several modules resolve config/cache paths during import, before the GUI
    launcher constructs QApplication. QStandardPaths uses applicationName for
    app-scoped locations, and Qt otherwise derives that name from the current
    executable once an application object exists. Reassert the RommHeld
    identity before every lookup so import order cannot move config/cache data.
    """
    if QCoreApplication.applicationName() != APP_NAME:
        QCoreApplication.setApplicationName(APP_NAME)


def _qt_location(location: QStandardPaths.StandardLocation, fallback: Path) -> Path:
    _ensure_application_identity()
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
    _ensure_application_identity()
    value = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation)
    return Path(value) / APP_NAME if value else cache_dir() / "tmp"


def is_web_url(value: str) -> bool:
    """Return whether *value* is a complete HTTP(S) URL suitable for desktop launch."""
    url = QUrl(value.strip())
    return bool(
        url.isValid()
        and url.scheme().lower() in {"http", "https"}
        and url.host()
    )


def _desktop_open_url(url: QUrl) -> bool:
    return bool(QDesktopServices.openUrl(url))


def open_external_url(value: str) -> bool:
    """Ask the desktop to open a validated web URL and report whether it accepted it."""
    value = value.strip()
    if not is_web_url(value):
        return False
    return _desktop_open_url(QUrl(value))


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
