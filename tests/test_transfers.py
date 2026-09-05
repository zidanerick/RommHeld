import threading
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from romm_vita_manager.transfers import copy_file_chunked


def test_cancelled_overwrite_preserves_existing_destination(tmp_path: Path):
    source = tmp_path / "source.bin"
    destination = tmp_path / "destination.bin"
    source.write_bytes(b"new-content" * 8)
    destination.write_bytes(b"known-good")
    cancel_event = threading.Event()

    def cancel_after_first_chunk(_done: int) -> None:
        cancel_event.set()

    copied = copy_file_chunked(
        source,
        destination,
        cancel_event,
        chunk_size=4,
        progress=cancel_after_first_chunk,
    )

    assert copied is False
    assert destination.read_bytes() == b"known-good"
    assert not list(tmp_path.glob(".*.rommheld-*.part"))


def test_cancelled_new_copy_leaves_no_partial_destination(tmp_path: Path):
    source = tmp_path / "source.bin"
    destination = tmp_path / "destination.bin"
    source.write_bytes(b"payload" * 8)
    cancel_event = threading.Event()
    cancel_event.set()

    copied = copy_file_chunked(source, destination, cancel_event, chunk_size=4)

    assert copied is False
    assert not destination.exists()
    assert not list(tmp_path.glob(".*.rommheld-*.part"))


def test_successful_overwrite_replaces_destination_after_copy(tmp_path: Path):
    source = tmp_path / "source.bin"
    destination = tmp_path / "destination.bin"
    payload = b"replacement-data" * 8
    source.write_bytes(payload)
    destination.write_bytes(b"old-data")

    copied = copy_file_chunked(
        source,
        destination,
        threading.Event(),
        chunk_size=5,
    )

    assert copied is True
    assert destination.read_bytes() == payload
    assert not list(tmp_path.glob(".*.rommheld-*.part"))


def test_short_read_preserves_existing_destination(tmp_path: Path):
    destination = tmp_path / "destination.bin"
    destination.write_bytes(b"known-good")

    class ShortSource:
        def stat(self):
            return SimpleNamespace(st_size=12)

        def open(self, _mode: str):
            return BytesIO(b"short")

    with pytest.raises(IOError, match="Source changed while copying"):
        copy_file_chunked(
            ShortSource(),
            destination,
            threading.Event(),
            chunk_size=4,
        )

    assert destination.read_bytes() == b"known-good"
    assert not list(tmp_path.glob(".*.rommheld-*.part"))