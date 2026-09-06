from __future__ import annotations

import ftplib
from pathlib import Path

import pytest

from romm_vita_manager.vita_ftp import (
    VitaFtpBackend,
    VitaFtpSettings,
    normalize_vita_ftp_path,
)


class FakeVitaFTP:
    files: dict[str, bytes] = {}
    dirs: set[str] = {"/", "/ux0:", "/ux0:/data"}

    def __init__(
        self,
        *args,
        fail_temp_size: bool = False,
        fail_final_size: bool = False,
        fail_stor: bool = False,
        fail_connect: bool = False,
        **kwargs,
    ):
        self.cwd_path = "/"
        self.rename_from = None
        self.closed = False
        self.fail_temp_size = fail_temp_size
        self.fail_final_size = fail_final_size
        self.fail_stor = fail_stor
        self.fail_connect = fail_connect
        self.final_rename_complete = False

    def connect(self, host, port, timeout=None):
        if self.fail_connect:
            raise ConnectionRefusedError("cleanup reconnect refused")
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
            if self.fail_temp_size and ".rommheld-" in path and path.endswith(".part"):
                self.fail_temp_size = False
                raise OSError("control connection lost during SIZE")
            if (
                self.fail_final_size
                and self.final_rename_complete
                and path == "/ux0:/data/game.bin"
            ):
                self.fail_final_size = False
                raise OSError("control connection lost during final SIZE")
            if path not in self.files:
                raise ftplib.error_perm("550 The file doesn't exist")
            return f"213: {len(self.files[path])}"
        if command.startswith("RNFR "):
            path = normalize_vita_ftp_path(command[5:])
            if path not in self.files:
                raise ftplib.error_perm("550 The file doesn't exist")
            self.rename_from = path
            return "250 Rename source accepted"
        raise ftplib.error_perm("502 command not implemented")

    def voidcmd(self, command):
        if command.startswith("MKD "):
            self.dirs.add(normalize_vita_ftp_path(command[4:]))
            return "226 Directory created"
        if command.startswith("DELE "):
            path = normalize_vita_ftp_path(command[5:])
            if path not in self.files:
                raise ftplib.error_perm("550 Could not delete file")
            del self.files[path]
            return "226 File deleted"
        if command.startswith("RNTO "):
            destination = normalize_vita_ftp_path(command[5:])
            if self.rename_from is None or self.rename_from not in self.files:
                raise ftplib.error_perm("550 Rename source missing")
            self.files[destination] = self.files.pop(self.rename_from)
            self.rename_from = None
            if destination == "/ux0:/data/game.bin":
                self.final_rename_complete = True
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
            if self.fail_stor:
                self.fail_stor = False
                raise OSError("Vita storage write failed")
        return "226 Transfer completed"

    def quit(self):
        self.closed = True
        return "221 Goodbye"

    def close(self):
        self.closed = True


class SequencedFactory:
    def __init__(self, *clients: dict[str, bool]):
        self.clients = list(clients)
        self.instances: list[FakeVitaFTP] = []

    def __call__(self, *args, **kwargs):
        options = self.clients.pop(0) if self.clients else {}
        client = FakeVitaFTP(*args, **kwargs, **options)
        self.instances.append(client)
        return client


@pytest.fixture(autouse=True)
def reset_fake_files():
    FakeVitaFTP.files = {}
    FakeVitaFTP.dirs = {"/", "/ux0:", "/ux0:/data"}


def backend(factory) -> VitaFtpBackend:
    result = VitaFtpBackend(
        VitaFtpSettings(host="192.0.2.20"),
        ftp_factory=factory,
    )
    result.connect()
    return result


def hidden_transfer_files() -> list[str]:
    return [path for path in FakeVitaFTP.files if ".rommheld-" in path]


def test_temp_size_connection_loss_cleans_staged_file_and_preserves_destination(tmp_path: Path):
    source = tmp_path / "game.bin"
    source.write_bytes(b"replacement-data")
    FakeVitaFTP.files["/ux0:/data/game.bin"] = b"known-good"
    factory = SequencedFactory({"fail_temp_size": True}, {})
    ftp_backend = backend(factory)

    with pytest.raises(OSError, match="control connection lost during SIZE"):
        ftp_backend.upload(source, "data/game.bin", overwrite=True)

    assert FakeVitaFTP.files["/ux0:/data/game.bin"] == b"known-good"
    assert hidden_transfer_files() == []
    assert not ftp_backend.connected
    assert len(factory.instances) == 2
    assert all(client.closed for client in factory.instances)


def test_stor_write_failure_cleans_partial_file_and_preserves_destination(tmp_path: Path):
    source = tmp_path / "game.bin"
    source.write_bytes(b"x" * (300 * 1024))
    FakeVitaFTP.files["/ux0:/data/game.bin"] = b"known-good"
    factory = SequencedFactory({"fail_stor": True}, {})
    ftp_backend = backend(factory)

    with pytest.raises(OSError, match="Vita storage write failed"):
        ftp_backend.upload(source, "data/game.bin", overwrite=True)

    assert FakeVitaFTP.files["/ux0:/data/game.bin"] == b"known-good"
    assert hidden_transfer_files() == []
    assert not ftp_backend.connected


def test_cleanup_reconnect_failure_does_not_mask_original_verification_error(tmp_path: Path):
    source = tmp_path / "game.bin"
    source.write_bytes(b"replacement-data")
    FakeVitaFTP.files["/ux0:/data/game.bin"] = b"known-good"
    factory = SequencedFactory({"fail_temp_size": True}, {"fail_connect": True})
    ftp_backend = backend(factory)

    with pytest.raises(OSError, match="control connection lost during SIZE"):
        ftp_backend.upload(source, "data/game.bin", overwrite=True)

    assert FakeVitaFTP.files["/ux0:/data/game.bin"] == b"known-good"
    assert len(hidden_transfer_files()) == 1
    assert not ftp_backend.connected
    assert len(factory.instances) == 2
    assert all(client.closed for client in factory.instances)


def test_final_size_connection_loss_reconnects_verifies_and_cleans_backup(tmp_path: Path):
    source = tmp_path / "game.bin"
    source.write_bytes(b"replacement-data")
    FakeVitaFTP.files["/ux0:/data/game.bin"] = b"known-good"
    factory = SequencedFactory({"fail_final_size": True}, {})
    ftp_backend = backend(factory)

    result, written = ftp_backend.upload(source, "data/game.bin", overwrite=True)

    assert result == "copied"
    assert written == len(b"replacement-data")
    assert FakeVitaFTP.files["/ux0:/data/game.bin"] == b"replacement-data"
    assert hidden_transfer_files() == []
    assert ftp_backend.connected
    assert len(factory.instances) == 2
    assert factory.instances[0].closed
    assert not factory.instances[1].closed

    ftp_backend.close()
    assert factory.instances[1].closed
