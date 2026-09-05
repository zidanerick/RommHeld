from __future__ import annotations

import shutil
from pathlib import Path

from .platform_services import writable_volumes

VITA_REQUIRED_MARKERS = ("app/VITASHELL", "VitaShell")
VITA_SUPPORTING_MARKERS = ("appmeta/VITASHELL", "data", "pspemu", "tai")


def is_vita_mount(mount: Path) -> bool:
    try:
        if not all((mount / marker).exists() for marker in VITA_REQUIRED_MARKERS):
            return False
        return any((mount / marker).exists() for marker in VITA_SUPPORTING_MARKERS)
    except OSError:
        return False


def find_vita_mounts() -> list[Path]:
    return [mount for mount in writable_volumes() if is_vita_mount(mount)]


def unique_vita_mount(mounts: list[Path]) -> Path | None:
    """Return a mount only when exactly one Vita USB candidate exists."""
    return mounts[0] if len(mounts) == 1 else None


def free_space(path: Path) -> int:
    return shutil.disk_usage(path).free


def total_space(path: Path) -> int:
    return shutil.disk_usage(path).total


def used_space(path: Path) -> int:
    usage = shutil.disk_usage(path)
    return usage.total - usage.free


__all__ = [
    "VITA_REQUIRED_MARKERS",
    "VITA_SUPPORTING_MARKERS",
    "find_vita_mounts",
    "free_space",
    "is_vita_mount",
    "total_space",
    "unique_vita_mount",
    "used_space",
]
