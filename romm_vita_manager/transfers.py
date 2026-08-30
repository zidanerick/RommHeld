from __future__ import annotations

import threading
from pathlib import Path


def copy_file_chunked(
    source: Path,
    destination: Path,
    cancel_event: threading.Event,
    chunk_size: int = 8 * 1024 * 1024,
    progress=None,
) -> bool:
    """Copy a file in cancellable chunks.

    Returns False when cancellation was requested. A cancelled partial destination
    is removed when possible.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    copied = 0
    try:
        with source.open("rb") as src, destination.open("wb") as dst:
            while True:
                if cancel_event.is_set():
                    return False
                chunk = src.read(chunk_size)
                if not chunk:
                    break
                dst.write(chunk)
                copied += len(chunk)
                if progress is not None:
                    progress(copied)
        return True
    finally:
        if cancel_event.is_set():
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass
