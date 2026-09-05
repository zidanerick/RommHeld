from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from .transfers import copy_file_chunked


def required_transfer_space(
    source_size: int,
    destination: Path,
    overwrite: bool = False,
) -> int:
    """Return free bytes required before a staged transfer can begin.

    Same-size destinations are skipped. A different-size destination needs no
    staging space until overwrite is explicitly approved. Once overwrite is
    approved, the complete source is staged beside the existing destination so
    cancellation can preserve the known-good file.
    """
    if destination.is_file():
        if destination.stat().st_size == source_size:
            return 0
        if not overwrite:
            return 0
    return source_size


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


__all__ = ["required_transfer_space", "transfer_file"]
