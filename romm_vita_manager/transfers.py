from __future__ import annotations

import threading
from pathlib import Path
from uuid import uuid4


def copy_file_chunked(
    source: Path,
    destination: Path,
    cancel_event: threading.Event,
    chunk_size: int = 8 * 1024 * 1024,
    progress=None,
) -> bool:
    """Copy a file in cancellable chunks without exposing a partial destination.

    Data is written to a temporary sibling, size-verified against the source
    snapshot, and moved into place only after the copy completes. Cancellation,
    verification failure, or another exception removes only the temporary file,
    preserving any existing destination.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(
        f".{destination.name}.rommheld-{uuid4().hex}.part"
    )
    expected_size = source.stat().st_size
    copied = 0
    try:
        if cancel_event.is_set():
            return False

        with source.open("rb") as src, temporary.open("wb") as dst:
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

        if cancel_event.is_set():
            return False
        if copied != expected_size:
            raise IOError(
                f"Source changed while copying: expected {expected_size} bytes, copied {copied} bytes."
            )

        temporary.replace(destination)
        return True
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass