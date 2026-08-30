from __future__ import annotations

import os
import shutil
from pathlib import Path


def find_vita_mounts() -> list[Path]:
    """Find likely VitaShell-mounted Vita filesystems without hard-coding a UUID."""
    base = Path("/run/media") / os.environ.get("USER", "")
    if not base.exists():
        return []

    found: list[Path] = []
    markers = ("app", "appmeta", "data", "pspemu", "tai", "VitaShell")
    for mount in sorted(base.iterdir()):
        if not mount.is_dir():
            continue
        if sum((mount / marker).exists() for marker in markers) >= 3:
            found.append(mount)
    return found


def free_space(path: Path) -> int:
    """Return free bytes on the filesystem containing path."""
    return shutil.disk_usage(path).free


def total_space(path: Path) -> int:
    return shutil.disk_usage(path).total


def used_space(path: Path) -> int:
    usage = shutil.disk_usage(path)
    return usage.total - usage.free
