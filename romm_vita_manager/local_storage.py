from __future__ import annotations

import os
from pathlib import Path


def resolve_storage_root(path: str | Path) -> Path:
    """Return an existing local directory suitable as a removable-storage root."""
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Storage root is not an existing directory: {root}")
    return root


def resolve_destination(root: str | Path, relative_path: str) -> Path:
    """Resolve a relative destination while keeping it inside the selected root."""
    base = resolve_storage_root(root)
    raw = relative_path.strip().replace("\\", "/")
    if raw.startswith("/"):
        raw = raw[1:]
    candidate = (base / raw).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError("Destination must remain inside the selected storage root.") from exc
    return candidate


def storage_summary(root: str | Path) -> tuple[int | None, int | None]:
    """Return total/free bytes where the host OS can report them."""
    base = resolve_storage_root(root)
    try:
        usage = os.statvfs(base)
    except OSError:
        return None, None
    total = usage.f_frsize * usage.f_blocks
    free = usage.f_frsize * usage.f_bavail
    return total, free
