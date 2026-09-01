from __future__ import annotations

from pathlib import Path
from typing import Callable

from .transfers import copy_file_chunked


def transfer_file(
    source: Path,
    destination: Path,
    cancel_event,
    progress: Callable[[int], None] | None = None,
) -> tuple[str, int]:
    """Transfer one arbitrary local file to an existing local/device-mounted path.

    Returns (result, bytes_written), where result is one of copied, skipped, or cancelled.
    The destination is never inferred from the source filename or extension.
    """
    if not source.is_file():
        raise FileNotFoundError(f"Source file does not exist: {source}")

    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.is_file() and destination.stat().st_size == source.stat().st_size:
        return "skipped", source.stat().st_size

    ok = copy_file_chunked(source, destination, cancel_event, progress=progress)
    if not ok:
        return "cancelled", 0

    if destination.stat().st_size != source.stat().st_size:
        raise IOError(
            f"Size verification failed: expected {source.stat().st_size} bytes, "
            f"got {destination.stat().st_size} bytes"
        )

    return "copied", source.stat().st_size
