from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class DeviceBackend(Protocol):
    key: str
    name: str

    def is_available(self) -> bool: ...


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


def mounted_vita_root() -> Path | None:
    """Find an already-mounted Vita without hard-coding username or mount UUID."""
    media = Path("/run/media")
    if not media.is_dir():
        return None
    for user_dir in media.iterdir():
        if not user_dir.is_dir():
            continue
        for mount in user_dir.iterdir():
            if mount.is_dir() and (mount / "ux0").exists():
                return mount
    return None
