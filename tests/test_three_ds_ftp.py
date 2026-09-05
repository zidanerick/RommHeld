from __future__ import annotations

from pathlib import Path

import ftplib
import pytest

from romm_vita_manager.three_ds_ftp import (
    ThreeDSFtpBackend,
    ThreeDSFtpSettings,
    describe_connection_error,
    join_remote_path,
    normalize_remote_path,
)


class FakeFTP:
    files: dict[str, bytes] = {}
    dirs: set[str] = {"/"}

    def __init__(self, *args, **kwargs):
        self.cwd_path = "/"
        self.logged_in = False
        self.closed = False

    def connect(self, host, port, timeout=None):
        self.host = host
        self.port = port

    def login(self, user, password):
        self.logged_in = True

    def set_pasv(self, passive):
        self.passive = passive

    def pwd(self):
        return self.cwd_path

    def cwd(self, path):
        path = normalize_remote_path(path)
        if path not in self.dirs:
            raise ftplib.error_perm("550 not a directory")
        self.cwd_path = path

    def mkd(self, path):
        path = normalize_remote_path(f"{self.cwd_path.rstrip('/')}/{path}")
        self.dirs.add(path)
        return path

    def mlsd(self, path):
        path = normalize_remote_path(path)
        if path not in self.dirs:
            raise ftplib.error_perm("550 not a directory")
        prefix = path.rstrip("/") + "/"
        for candidate in sorted(self.dirs):
            if candidate.startswith(prefix):
                remainder = candidate[len(prefix):].strip("/")
                if remainder and "/" not in remainder:
                    yield remainder, {"type": "dir"}
        for candidate, data in sorted(self.files.items()):
            if candidate.startswith(prefix):
                remainder = candidate[len(prefix):].strip("/")
                if remainder and "/" not in remainder:
                    yield remainder, {"type": "file", "size": str(len(data))}

    def nlst(self, path):
        return [f"{path.rstrip('/')}/{name}" for name, _ in self.mlsd(path)]

    def size(self, path):
        path = normalize_remote_path(path)
        if path not in self.files:
            raise ftplib.error_perm("550 not found")
        return len(self.files[path])

    def sendcmd(self, command):
        if command == "SITE AVBL":
            return "213 123456789"
        raise ftplib.error_perm("500 unsupported command")

    def storbinary(self, command, fp, blocksize=8192, callback=None, rest=None):
        path = command.removeprefix("STOR ")
        existing = self.files.get(path, b"")
        prefix = existing[:rest] if rest else b""
        chunks = []
        while True:
            chunk = fp.read(blocksize)
            if not chunk:
                break
            chunks.append(chunk)
            if callback:
                callback(chunk)
        self.files[path] = prefix + b"".join(chunks)

    def abort(self):
        pass

    def quit(self):
        pass

    def close(self):
        self.closed = True


class NoRestFTP(FakeFTP):
    def storbinary(self, command, fp, blocksize=8192, callback=None, rest=None):
        if rest:
            raise ftplib.error_perm("500 REST not implemented")
        return super().storbinary(command, fp, blocksize=blocksize, callback=callback, rest=rest)


class LoginFailureFTP(FakeFTP):
    last_instance = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        type(self).last_instance = self

    def login(self, user, password):
        raise ftplib.error_perm("530 Login incorrect")


@pytest.fixture(autouse=True)
def reset_fake():
    FakeFTP.files = {}
    FakeFTP.dirs = {"/"}
    LoginFailureFTP.last_instance = None


def make_backend(remote_root: str = "/", ftp_factory=FakeFTP) -> ThreeDSFtpBackend:
    backend = ThreeDSFtpBackend(
        ThreeDSFtpSettings(host="192.0.2.10", remote_root=remote_root),
        ftp_factory=ftp_factory,
    )
    backend.connect()
    return backend


def test_normalize_remote_path_rejects_traversal():
    assert normalize_remote_path("/roms/test.nds") == "/roms/test.nds"
    with pytest.raises(ValueError):
        normalize_remote_path("/roms/../secret.nds")


def test_join_remote_path_stays_inside_root():
    assert join_remote_path("/roms", "game.nds") == "/roms/game.nds"
    with pytest.raises(ValueError):
        join_remote_path("/roms", "/outside.nds")
    with pytest.raises(ValueError):
        join_remote_path("/roms", "../outside.nds")


def test_backend_enforces_configured_root(tmp_path: Path):
    source = tmp_path / "test.bin"
    source.write_bytes(b"data")
    FakeFTP.dirs.add("/roms")
    backend = make_backend("/roms")

    result, _ = backend.upload(source, "game.bin")
    assert result == "copied"
    assert FakeFTP.files["/roms/game.bin"] == b"data"

    with pytest.raises(ValueError):
        backend.upload(source, "/outside/game.bin")


def test_backend_connects_with_configured_endpoint():
    backend = make_backend()
    assert backend.connected
    assert backend.ftp.logged_in
    assert backend.ftp.host == "192.0.2.10"
    assert backend.ftp.port == 5000


def test_failed_login_closes_partial_connection():
    backend = ThreeDSFtpBackend(
        ThreeDSFtpSettings(host="192.0.2.10"),
        ftp_factory=LoginFailureFTP,
    )

    with pytest.raises(ftplib.error_perm, match="530"):
        backend.connect()

    assert not backend.connected
    assert LoginFailureFTP.last_instance is not None
    assert LoginFailureFTP.last_instance.closed


def test_connection_errors_include_console_side_remediation():
    assert "Open ftpd" in describe_connection_error(ConnectionRefusedError("refused"))
    assert "same local network" in describe_connection_error(TimeoutError("timed out"))
    assert "username and password" in describe_connection_error(ftplib.error_perm("530 Login incorrect"))


def test_upload_and_skip_same_size(tmp_path: Path):
    source = tmp_path / "test.nds"
    source.write_bytes(b"hello 3ds")
    backend = make_backend()

    result, written = backend.upload(source, "/roms/test.nds")
    assert result == "copied"
    assert written == source.stat().st_size

    result, _ = backend.upload(source, "/roms/test.nds")
    assert result == "skipped"


def test_upload_can_resume_partial_remote_file(tmp_path: Path):
    source = tmp_path / "test.bin"
    source.write_bytes(b"0123456789")
    FakeFTP.files["/roms/test.bin"] = b"0123"
    FakeFTP.dirs.add("/roms")
    backend = make_backend()

    result, written = backend.upload(source, "/roms/test.bin", resume=True)
    assert result == "resumed"
    assert written == len(source.read_bytes())
    assert FakeFTP.files["/roms/test.bin"] == source.read_bytes()


def test_upload_falls_back_to_fresh_copy_when_rest_is_unsupported(tmp_path: Path):
    source = tmp_path / "test.bin"
    source.write_bytes(b"0123456789")
    FakeFTP.files["/roms/test.bin"] = b"0123"
    FakeFTP.dirs.add("/roms")
    backend = make_backend(ftp_factory=NoRestFTP)

    result, written = backend.upload(source, "/roms/test.bin", resume=True)
    assert result == "copied"
    assert written == len(source.read_bytes())
    assert FakeFTP.files["/roms/test.bin"] == source.read_bytes()


def test_different_size_is_not_overwritten_by_default(tmp_path: Path):
    source = tmp_path / "test.bin"
    source.write_bytes(b"0123456789")
    FakeFTP.files["/roms/test.bin"] = b"different"
    FakeFTP.dirs.add("/roms")
    backend = make_backend()

    result, _ = backend.upload(source, "/roms/test.bin", resume=False)
    assert result == "different"
    assert FakeFTP.files["/roms/test.bin"] == b"different"


def test_directory_listing_returns_dirs_first():
    FakeFTP.dirs.update({"/roms", "/roms/gba"})
    FakeFTP.files["/roms/game.gba"] = b"data"
    backend = make_backend()
    entries = backend.list_directory("/roms")
    assert entries[0]["name"] == "gba"
    assert entries[0]["type"] == "dir"
    assert entries[1]["name"] == "game.gba"


def test_available_space_is_best_effort():
    backend = make_backend()
    assert backend.available_space() == 123456789
