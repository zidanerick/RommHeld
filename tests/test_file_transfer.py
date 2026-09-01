from __future__ import annotations

import threading

from romm_vita_manager.file_transfer import transfer_file


def test_transfer_file_copies_and_verifies(tmp_path):
    source = tmp_path / "thing.bin"
    destination = tmp_path / "remote" / "thing.bin"
    payload = b"hello rommheld" * 1024
    source.write_bytes(payload)

    result, written = transfer_file(source, destination, threading.Event())

    assert result == "copied"
    assert written == len(payload)
    assert destination.read_bytes() == payload


def test_transfer_file_skips_same_size(tmp_path):
    source = tmp_path / "thing.bin"
    destination = tmp_path / "remote.bin"
    payload = b"same-size"
    source.write_bytes(payload)
    destination.write_bytes(payload)

    result, written = transfer_file(source, destination, threading.Event())

    assert result == "skipped"
    assert written == len(payload)


def test_transfer_file_refuses_different_size_without_overwrite(tmp_path):
    source = tmp_path / "source.bin"
    destination = tmp_path / "remote.bin"
    source.write_bytes(b"new payload")
    destination.write_bytes(b"old")

    result, written = transfer_file(source, destination, threading.Event())

    assert result == "different"
    assert written == 0
    assert destination.read_bytes() == b"old"


def test_transfer_file_allows_explicit_overwrite(tmp_path):
    source = tmp_path / "source.bin"
    destination = tmp_path / "remote.bin"
    source.write_bytes(b"new payload")
    destination.write_bytes(b"old")

    result, written = transfer_file(source, destination, threading.Event(), overwrite=True)

    assert result == "copied"
    assert written == source.stat().st_size
    assert destination.read_bytes() == b"new payload"
