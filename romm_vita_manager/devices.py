from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .vita import find_vita_mounts


@dataclass(frozen=True)
class DeviceInfo:
    key: str
    name: str
    transport: str
    description: str


DEVICE_TYPES = (
    DeviceInfo("vita", "PlayStation Vita", "USB / VitaShell", "Mounted VitaShell filesystem."),
    DeviceInfo("3ds", "Nintendo 3DS", "FTP", "3DS filesystem exposed by an FTP server."),
)


def available_devices() -> tuple[DeviceInfo, ...]:
    """Return supported device types in the UI-facing order."""
    return DEVICE_TYPES


def mounted_vita_root() -> Path | None:
    """Return the first dynamically detected VitaShell mount, if any."""
    mounts = find_vita_mounts()
    return mounts[0] if mounts else None
