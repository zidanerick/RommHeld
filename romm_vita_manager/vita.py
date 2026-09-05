from __future__ import annotations

import shutil
from pathlib import Path

from .platform_services import writable_volumes


VITA_REQUIRED_MARKERS = (
    "app/VITASHELL",
    "VitaShell",
)
VITA_SUPPORTING_MARKERS = (
    "appmeta/VITASHELL",
    "data",
    "pspemu",
    "tai",
)


def is_vita_mount(mount: Path) -> bool:
    """Return whether a mounted filesystem has strong VitaShell ux0 evidence.

    VitaShell USB exposes a selectable physical storage device. Requiring both
    the VitaShell application and its ux0 data directory avoids treating an
    arbitrary removable filesystem with a few Vita-like folder names as a Vita.
    Supporting markers add one more piece of expected ux0 structure.
    """
    try:
        if not all((mount / marker).exists() for marker in VITA_REQUIRED_MARKERS):
            return False
        return any((mount / marker).exists() for marker in VITA_SUPPORTING_MARKERS)
    except OSError:
        return False


def find_vita_mounts() -> list[Path]:
    """Find likely VitaShell-mounted ux0 backing filesystems."""
    return [mount for mount in writable_volumes() if is_vita_mount(mount)]


def free_space(path: Path) -> int:
    """Return free bytes on the filesystem containing path."""
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
    "used_space",
]
