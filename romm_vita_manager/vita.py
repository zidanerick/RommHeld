from __future__ import annotations

import shutil
from pathlib import Path

from .platform_services import writable_volumes


VITA_MARKERS = (
    "app",
    "appmeta",
    "data",
    "pspemu",
    "tai",
    "VitaShell",
)


def find_vita_mounts() -> list[Path]:
    """Find likely VitaShell-mounted filesystems without OS-specific mount paths."""
    found: list[Path] = []
    for mount in writable_volumes():
        try:
            if sum((mount / marker).exists() for marker in VITA_MARKERS) >= 3:
                found.append(mount)
        except OSError:
            continue
    return found


def free_space(path: Path) -> int:
    """Return free bytes on the filesystem containing path."""
    return shutil.disk_usage(path).free


def total_space(path: Path) -> int:
    return shutil.disk_usage(path).total


def used_space(path: Path) -> int:
    usage = shutil.disk_usage(path)
    return usage.total - usage.free
