from pathlib import Path

import pytest

from romm_vita_manager.ftp_filesystem import (
    ThreeDSFtpFilesystemAdapter,
    VitaFtpFilesystemAdapter,
    ftp_filesystem_for_console,
    parse_vita_list_line,
)
from romm_vita_manager.three_ds_ftp import ThreeDSFtpSettings
from romm_vita_manager.vita_ftp import VitaFtpSettings


class FakeFtp:
    def __init__(self, payload=b"payload"):
        self.payload = payload
        self.renames = []
        self.deleted = []
        self.removed = []
        self.aborted = False
        self.list_lines = []

    def retrbinary(self, command, callback, blocksize=8192):
        assert command.startswith("RETR ")
        midpoint = max(1, len(self.payload) // 2)
        callback(self.payload[:midpoint])
        callback(self.payload[midpoint:])

    def retrlines(self, command, callback):
        assert command.startswith("LIST ")
        for line in self.list_lines:
            callback(line)
        return "226 Transfer complete."

    def rename(self, source, destination):
        self.renames.append((source, destination))

    def delete(self, path):
        self.deleted.append(path)

    def rmd(self, path):
        self.removed.append(path)

    def voidcmd(self, command):
        if command.startswith("RMD "):
            self.removed.append(command[4:])
        return "250 OK"

    def abort(self):
        self.aborted = True


class FakeThreeDSBackend:
    def __init__(self, settings, payload=b"payload"):
        self.settings = settings
        self.ftp = FakeFtp(payload)
        self.closed = False
        self.upload_calls = []
        self.directories = []

    def connect(self):
        return "/"

    def close(self):
        self.closed = True

    def _require_connection(self):
        return self.ftp

    def _rooted_path(self, path):
        clean = path.strip("/")
        return "/" + clean if clean else "/"

    def list_directory(self, path=""):
        return [
            {"name": "folder", "type": "dir", "size": 0},
            {"name": "game file.3dsx", "type": "file", "size": 12},
        ]

    def upload(self, source, remote_path, **kwargs):
        self.upload_calls.append((source, remote_path, kwargs))
        return "copied", source.stat().st_size

    def remote_size(self, path):
        return len(self.ftp.payload)

    def ensure_directory(self, path):
        self.directories.append(path)

    def available_space(self):
        return 123456


class FakeVitaBackend:
    def __init__(self, settings, payload=b"vita"):
        self.settings = settings
        self.ftp = FakeFtp(payload)
        self.ftp.list_lines = [
            "drwxr-xr-x 1 vita vita 0 Sep 6 12:34 data",
            "-rw-r--r-- 1 vita vita 123 Sep 6 12:35 game file.bin",
        ]
        self.dropped = False
        self.renames = []
        self.deleted = []
        self.directories = []

    def connect(self):
        return "/ux0:"

    def close(self):
        pass

    def _require_connection(self):
        return self.ftp

    def _rooted_path(self, path):
        clean = path.strip("/")
        return "/ux0:/" + clean if clean else "/ux0:"

    def remote_size(self, path):
        return len(self.ftp.payload)

    def upload(self, source, remote_path, **kwargs):
        return "copied", source.stat().st_size

    def ensure_directory(self, path):
        self.directories.append(path)

    def _rename(self, source, destination):
        self.renames.append((source, destination))

    def _delete(self, ftp, path):
        self.deleted.append(path)

    def _drop_connection(self):
        self.dropped = True


def test_vita_list_parser_matches_ftpvitalib_format_and_preserves_spaces():
    assert parse_vita_list_line(
        "drwxr-xr-x 1 vita vita 0 Sep 6 12:34 Saved Data"
    ) == ("Saved Data", "dir", 0)
    assert parse_vita_list_line(
        "-rw-r--r-- 1 vita vita 4294967295 Sep 6 12:35 large file.bin"
    ) == ("large file.bin", "file", 4294967295)
    assert parse_vita_list_line("unexpected") is None


def test_three_ds_adapter_exposes_protocol_specific_capabilities():
    adapter = ThreeDSFtpFilesystemAdapter(
        ThreeDSFtpSettings("192.0.2.3"),
        backend_factory=FakeThreeDSBackend,
    )

    assert adapter.capabilities.resume_upload
    assert adapter.capabilities.free_space
    assert adapter.capabilities.remove_empty_directory
    assert not hasattr(adapter, "remove_tree")


def test_vita_adapter_disables_resume_and_free_space_claims():
    adapter = VitaFtpFilesystemAdapter(
        VitaFtpSettings("192.0.2.4"),
        backend_factory=FakeVitaBackend,
    )

    assert not adapter.capabilities.resume_upload
    assert not adapter.capabilities.free_space
    assert adapter.available_space() is None


def test_three_ds_listing_returns_root_relative_entries():
    adapter = ThreeDSFtpFilesystemAdapter(
        ThreeDSFtpSettings("192.0.2.3"),
        backend_factory=FakeThreeDSBackend,
    )
    adapter.connect()

    entries = adapter.list_directory("3ds")

    assert [(entry.name, entry.path, entry.kind, entry.size) for entry in entries] == [
        ("folder", "3ds/folder", "dir", 0),
        ("game file.3dsx", "3ds/game file.3dsx", "file", 12),
    ]


def test_vita_listing_uses_list_not_unsupported_mlsd_or_nlst():
    adapter = VitaFtpFilesystemAdapter(
        VitaFtpSettings("192.0.2.4"),
        backend_factory=FakeVitaBackend,
    )
    adapter.connect()

    entries = adapter.list_directory("data")

    assert [(entry.name, entry.path, entry.kind, entry.size) for entry in entries] == [
        ("data", "data/data", "dir", 0),
        ("game file.bin", "data/game file.bin", "file", 123),
    ]


def test_download_is_atomic_and_size_verified(tmp_path: Path):
    adapter = ThreeDSFtpFilesystemAdapter(
        ThreeDSFtpSettings("192.0.2.3"),
        backend_factory=FakeThreeDSBackend,
    )
    adapter.connect()
    destination = tmp_path / "download.bin"
    destination.write_bytes(b"old")

    result, size = adapter.download("remote.bin", destination, overwrite=True)

    assert result == "downloaded"
    assert size == len(b"payload")
    assert destination.read_bytes() == b"payload"
    assert not list(tmp_path.glob("*.part"))


def test_download_refuses_existing_local_destination_without_overwrite(tmp_path: Path):
    adapter = ThreeDSFtpFilesystemAdapter(
        ThreeDSFtpSettings("192.0.2.3"),
        backend_factory=FakeThreeDSBackend,
    )
    adapter.connect()
    destination = tmp_path / "download.bin"
    destination.write_bytes(b"keep")

    with pytest.raises(FileExistsError):
        adapter.download("remote.bin", destination)

    assert destination.read_bytes() == b"keep"


def test_vita_cancelled_download_drops_control_connection_and_preserves_destination(tmp_path: Path):
    import threading

    backend_holder = {}

    def factory(settings):
        backend = FakeVitaBackend(settings, payload=b"abcdefgh")
        original = backend.ftp.retrbinary

        def cancel_after_first(command, callback, blocksize=8192):
            def wrapped(chunk):
                callback(chunk)
                event.set()
            original(command, wrapped, blocksize)

        backend.ftp.retrbinary = cancel_after_first
        backend_holder["backend"] = backend
        return backend

    event = threading.Event()
    adapter = VitaFtpFilesystemAdapter(VitaFtpSettings("192.0.2.4"), backend_factory=factory)
    adapter.connect()
    destination = tmp_path / "download.bin"
    destination.write_bytes(b"keep")

    with pytest.raises(InterruptedError):
        adapter.download("remote.bin", destination, overwrite=True, cancel_event=event)

    assert destination.read_bytes() == b"keep"
    assert backend_holder["backend"].dropped


def test_file_mutations_are_explicit_and_empty_directory_only():
    adapter = ThreeDSFtpFilesystemAdapter(
        ThreeDSFtpSettings("192.0.2.3"),
        backend_factory=FakeThreeDSBackend,
    )
    adapter.connect()

    adapter.make_directory("roms/new")
    adapter.rename("old.bin", "new.bin")
    adapter.delete_file("new.bin")
    adapter.remove_directory("roms/empty")

    assert adapter.backend.directories == ["roms/new"]
    assert adapter.backend.ftp.renames == [("/old.bin", "/new.bin")]
    assert adapter.backend.ftp.deleted == ["/new.bin"]
    assert adapter.backend.ftp.removed == ["/roms/empty"]


def test_console_factory_rejects_wrong_settings_and_unsupported_devices():
    assert isinstance(
        ftp_filesystem_for_console("3ds", ThreeDSFtpSettings("192.0.2.3")),
        ThreeDSFtpFilesystemAdapter,
    )
    assert isinstance(
        ftp_filesystem_for_console("PlayStation TV", VitaFtpSettings("192.0.2.4")),
        VitaFtpFilesystemAdapter,
    )

    with pytest.raises(TypeError):
        ftp_filesystem_for_console("3ds", VitaFtpSettings("192.0.2.4"))
    with pytest.raises(ValueError):
        ftp_filesystem_for_console("Nintendo DS", ThreeDSFtpSettings("192.0.2.3"))
