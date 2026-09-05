from __future__ import annotations

import re
from pathlib import Path


_VITA_VOLUME_RE = re.compile(r"^[A-Za-z0-9_]+:/")


def vita_target(vita: Path, remote_path: str) -> Path:
    """Resolve a VitaShell ux0 path beneath the mounted ux0 filesystem."""
    raw = remote_path.strip().replace("\\", "/")
    lowered = raw.lower()
    if lowered in {"ux0", "ux0:", "ux0:/"}:
        raw = ""
    elif lowered.startswith("ux0:/"):
        raw = raw[5:]
    elif lowered.startswith("ux0/"):
        raw = raw[4:]
    elif _VITA_VOLUME_RE.match(raw):
        raise ValueError("Destination must use the mounted Vita ux0 filesystem.")

    base = vita.expanduser().resolve()
    target = (base / Path(raw)).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Destination must remain inside the Vita ux0 filesystem.") from exc
    return target


__all__ = ["vita_target"]