from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from .transfers import copy_file_chunked


def transfer_file(
    source: Path,
    destination: Path,
    cancel_event: threading.Event,
    progress: Callable[[int], None] | None = None,
    overwrite: bool = False,
) -> tuple[str, int]:
    """Transfer one arbitrary local file to a mounted-device path."""
    if not source.is_file():
        raise FileNotFoundError(f"Source file does not exist: {source}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    source_size = source.stat().st_size

    if destination.is_file():
        destination_size = destination.stat().st_size
        if destination_size == source_size:
            return "skipped", source_size
        if not overwrite:
            return "different", 0

    ok = copy_file_chunked(source, destination, cancel_event, progress=progress)
    if not ok:
        return "cancelled", 0

    final_size = destination.stat().st_size
    if final_size != source_size:
        raise IOError(
            f"Size verification failed: expected {source_size} bytes, got {final_size} bytes"
        )

    return "copied", source_size
