from __future__ import annotations

import ftplib
import threading
from pathlib import Path

import pytest

from romm_vita_manager.vita_ftp import (
    VitaFtpBackend,
    VitaFtpConnectionError,
    VitaFtpSettings,
    join_vita_ftp_path,
    normalize_vita_ftp_path,
)


class FakeVitaFTP:
    files: dict[str, bytes] = {}
    dirs: set[str] = {"/", "/ux0:"}
    last_instance = None

    def __init__(self, *args, **kwargs):
        type(self).last_instance = self
        self.cwd_path = "/"
        self.rename_from = None
        self.closed = False

    def connect(self, host, port, timeout=None):
        self.host = host
        self.port = port

    def login(self, user, password):
        self.user = user

    def set_pasv(self, passive):
        self.passive = passive

    def pwd(self):
        return self.cwd_path

    def cwd(self, path):
        path = normalize_vita_ftp_path(path)
        if path not in self.dirs:
            raise ftplib.error_perm("550 Invalid directory")
        self.cwd_path = path

    def sendcmd(self, command):
        if command.startswith("SIZE "):
            path = normalize_vita_ftp_path(command[5:])
            if path not in self.files:
                raise ftplib.error_perm("550 The file doesn't exist")
            return f"213: {len(self.files[path])}"
        if command.startswith("RNFR "):
            path = normalize_vita_ftp_path(command[5:])
            if path not in self.files:
                raise ftplib.error_perm("550 The file doesn't exist")
            self.rename_from = path
            return "250 I need the destination name"
        raise ftplib.error_perm("502 command not implemented")

    def voidcmd(self, command):
        if command.startswith("MKD "):
            path = normalize_vita_ftp_path(command[4:])
            self.dirs.add(path)
            return "226 Directory created"
        if command.startswith("DELE "):
            path = normalize_vita_ftp_path(command[5:])
            if path not in self.files:
                raise ftplib.error_perm("550 Could not delete the file")
            del self.files[path]
            return "226 File deleted"
        if command.startswith("RNTO "):
            destination = normalize_vita_ftp_path(command[5:])
            if self.rename_from is None or self.rename_from not in self.files:
                raise ftplib.error_perm("550 Error renaming the file")
            self.files[destination] = self.files.pop(self.rename_from)
            self.rename_from = None
            return "226 Rename completed"
        raise ftplib.error_perm("502 command not implemented")

    def storbinary(self, command, fp, blocksize=8192, callback=None, rest=None):
        assert rest is None
        path = normalize_vita_ftp_path(command.removeprefix("STOR "))
        self.files[path] = b""
        while True:
            chunk = fp.read(blocksize)
            if not chunk:
                break
            self.files[path] += chunk
            if callback:
                callback(chunk)
        return "226 Transfer completed"

    def quit(self):
        self.closed = True
        return "221 Goodbye"

    def close(self):
        self.closed = True


class RefusedVitaFTP(FakeVitaFTP):
    def connect(self, host, port, timeout=None):
        raise ConnectionRefusedError("refused")


class FailFinalRenameVitaFTP(FakeVitaFTP):
    fail_final_rename = True

    def voidcmd(self, command):
        if command.startswith("RNTO "):
            destination = normalize_vita_ftp_path(command[5:])
            if (
                type(self).fail_final_rename
                and self.rename_from is not None
                and ".part" in self.rename_from
                and destination == "/ux0:/data/game.bin"
            ):
                type(self).fail_final_rename = False
                raise ftplib.error_perm("550 simulated final rename failure")
        return super().voidcmd(command)


class BadFinalSizeVitaFTP(FakeVitaFTP):
    corrupt_final_size = False

    def sendcmd(self, command):
        if command == "SIZE /ux0:/data/game.bin" and type(self).corrupt_final_size:
            return "213: 1"
        return super().sendcmd(command)

    def voidcmd(self, command):
        result = super().voidcmd(command)
        if command == "RNTO /ux0:/data/game.bin":
            type(self).corrupt_final_size = True
        if command == "DELE /ux0:/data/game.bin":
            type(self).corrupt_final_size = False
        return result


@pytest.fixture(autouse=True)
def reset_fake():
    FakeVitaFTP.files = {}
    FakeVitaFTP.dirs = {"/", "/ux0:"}
    FakeVitaFTP.last_instance = None
    FailFinalRenameVitaFTP.fail_final_rename = True
    BadFinalSizeVitaFTP.corrupt_final_size = False


def make_backend(ftp_factory=FakeVitaFTP) -> VitaFtpBackend:
    backend = VitaFtpBackend(
        VitaFtpSettings(host="192.0.2.20"),
        ftp_factory=ftp_factory,
    )
    backend.connect()
    return backend


def test_vita_ftp_paths_are_constrained_to_ux0():
    assert normalize_vita_ftp_path("ux0:/data/game.bin") == "/ux0:/data/game.bin"
    assert join_vita_ftp_path("/ux0:", "data/game.bin") == "/ux0:/data/game.bin"
    with pytest.raises(ValueError):
        join_vita_ftp_path("/ux0:", "uma0:/game.bin")
    with pytest.raises(ValueError):
        join_vita_ftp_path("/ux0:", "../game.bin")


def test_connect_uses_vitashell_default_port_and_ux0_root():
    backend = make_backend()
    assert backend.connected
    assert backend.ftp.port == 1337
    assert backend.ftp.cwd_path == "/ux0:"


def test_connection_failure_closes_socket_and_explains_vitashell():
    backend = VitaFtpBackend(
        VitaFtpSettings(host="192.0.2.20"),
        ftp_factory=RefusedVitaFTP,
    )
    with pytest.raises(VitaFtpConnectionError, match="Start FTP in VitaShell"):
        backend.connect()
    assert not backend.connected
    assert RefusedVitaFTP.last_instance is not None
    assert RefusedVitaFTP.last_instance.closed


def test_remote_size_parses_vitashell_nonstandard_size_reply():
    FakeVitaFTP.files["/ux0:/data/game.bin"] = b"12345"
    FakeVitaFTP.dirs.add("/ux0:/data")
    backend = make_backend()
    assert backend.remote_size("data/game.bin") == 5


def test_upload_creates_directories_verifies_and_renames(tmp_path: Path):
    source = tmp_path / "game.bin"
    source.write_bytes(b"vita-data")
    backend = make_backend()

    result, written = backend.upload(source, "data/rommheld/game.bin")

    assert result == "copied"
    assert written == len(b"vita-data")
    assert FakeVitaFTP.files["/ux0:/data/rommheld/game.bin"] == b"vita-data"
    assert not any(".rommheld-" in path for path in FakeVitaFTP.files)


def test_same_size_is_skipped_and_different_size_needs_overwrite(tmp_path: Path):
    source = tmp_path / "game.bin"
    source.write_bytes(b"12345")
    FakeVitaFTP.dirs.add("/ux0:/data")
    FakeVitaFTP.files["/ux0:/data/game.bin"] = b"abcde"
    backend = make_backend()

    result, _ = backend.upload(source, "data/game.bin")
    assert result == "skipped"

    source.write_bytes(b"123456")
    result, _ = backend.upload(source, "data/game.bin")
    assert result == "different"
    assert FakeVitaFTP.files["/ux0:/data/game.bin"] == b"abcde"


def test_overwrite_replaces_only_after_verified_temp_upload(tmp_path: Path):
    source = tmp_path / "game.bin"
    source.write_bytes(b"new-content")
    FakeVitaFTP.dirs.add("/ux0:/data")
    FakeVitaFTP.files["/ux0:/data/game.bin"] = b"old"
    backend = make_backend()

    result, _ = backend.upload(source, "data/game.bin", overwrite=True)

    assert result == "copied"
    assert FakeVitaFTP.files["/ux0:/data/game.bin"] == b"new-content"
    assert not any(".rommheld-" in path for path in FakeVitaFTP.files)


def test_failed_final_rename_restores_existing_destination(tmp_path: Path):
    source = tmp_path / "game.bin"
    source.write_bytes(b"new-content")
    FakeVitaFTP.dirs.add("/ux0:/data")
    FakeVitaFTP.files["/ux0:/data/game.bin"] = b"old"
    backend = make_backend(FailFinalRenameVitaFTP)

    with pytest.raises(ftplib.error_perm, match="simulated final rename failure"):
        backend.upload(source, "data/game.bin", overwrite=True)

    assert FakeVitaFTP.files["/ux0:/data/game.bin"] == b"old"
    assert not any(".rommheld-" in path for path in FakeVitaFTP.files)


def test_failed_final_verification_removes_new_bad_destination(tmp_path: Path):
    source = tmp_path / "game.bin"
    source.write_bytes(b"new-content")
    FakeVitaFTP.dirs.add("/ux0:/data")
    backend = make_backend(BadFinalSizeVitaFTP)

    with pytest.raises(IOError, match="final|expected"):
        backend.upload(source, "data/game.bin")

    assert "/ux0:/data/game.bin" not in FakeVitaFTP.files
    assert not any(".rommheld-" in path for path in FakeVitaFTP.files)


def test_cancelled_upload_preserves_existing_destination(tmp_path: Path):
    source = tmp_path / "game.bin"
    source.write_bytes(b"x" * (300 * 1024))
    FakeVitaFTP.dirs.add("/ux0:/data")
    FakeVitaFTP.files["/ux0:/data/game.bin"] = b"existing"
    cancel = threading.Event()
    backend = make_backend()

    result, transferred = backend.upload(
        source,
        "data/game.bin",
        overwrite=True,
        cancel_event=cancel,
        progress=lambda _done: cancel.set(),
    )

    assert result == "cancelled"
    assert transferred > 0
    assert FakeVitaFTP.files["/ux0:/data/game.bin"] == b"existing"
    assert not any(".rommheld-" in path for path in FakeVitaFTP.files)
    assert not backend.connected
