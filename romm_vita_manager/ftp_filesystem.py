from __future__ import annotations

import ftplib
import os
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .three_ds_ftp import ThreeDSFtpBackend, ThreeDSFtpSettings
from .vita_ftp import VitaFtpBackend, VitaFtpSettings


ProgressCallback = Callable[[int], None]


@dataclass(frozen=True)
class RemoteFilesystemCapabilities:
    list_directory: bool = True
    download: bool = True
    upload: bool = True
    create_directory: bool = True
    rename: bool = True
    delete_file: bool = True
    remove_empty_directory: bool = True
    resume_upload: bool = False
    free_space: bool = False


@dataclass(frozen=True)
class RemoteEntry:
    name: str
    path: str
    kind: str
    size: int = 0

    def __post_init__(self) -> None:
        if self.kind not in {"file", "dir"}:
            raise ValueError(f"Unknown remote entry kind: {self.kind}")
        if not self.name or self.name in {".", ".."}:
            raise ValueError(f"Invalid remote entry name: {self.name!r}")
        if self.size < 0:
            raise ValueError("Remote entry size cannot be negative.")

    @property
    def is_dir(self) -> bool:
        return self.kind == "dir"


class RemoteFilesystemError(RuntimeError):
    pass


def _relative_child(parent: str, name: str) -> str:
    parent = parent.strip("/")
    if name in {"", ".", ".."} or "/" in name or "\\" in name:
        raise ValueError(f"Unsafe remote entry name: {name!r}")
    return posixpath.join(parent, name) if parent else name


def _atomic_download_target(destination: Path) -> Path:
    return destination.with_name(
        f".{destination.name}.rommheld-{uuid4().hex}.part"
    )


class _BaseFtpFilesystemAdapter:
    display_name = "FTP"
    capabilities = RemoteFilesystemCapabilities()

    def connect(self) -> str:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def list_directory(self, path: str = "") -> list[RemoteEntry]:
        raise NotImplementedError

    def upload(
        self,
        source: Path,
        remote_path: str,
        *,
        overwrite: bool = False,
        cancel_event=None,
        progress: ProgressCallback | None = None,
    ) -> tuple[str, int]:
        raise NotImplementedError

    def _download_client_and_path(self, remote_path: str):
        raise NotImplementedError

    def _remote_size(self, remote_path: str) -> int | None:
        raise NotImplementedError

    def _cancel_download(self) -> None:
        pass

    def download(
        self,
        remote_path: str,
        destination: Path,
        *,
        overwrite: bool = False,
        cancel_event=None,
        progress: ProgressCallback | None = None,
    ) -> tuple[str, int]:
        destination = destination.expanduser()
        if destination.exists() and not overwrite:
            raise FileExistsError(f"Local destination already exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = _atomic_download_target(destination)
        expected_size = self._remote_size(remote_path)
        transferred = 0

        client, full_remote = self._download_client_and_path(remote_path)

        def callback(chunk: bytes) -> None:
            nonlocal transferred
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("FTP download cancelled.")
            handle.write(chunk)
            transferred += len(chunk)
            if progress is not None:
                progress(transferred)

        try:
            with temporary.open("wb") as handle:
                try:
                    client.retrbinary(
                        f"RETR {full_remote}",
                        callback,
                        blocksize=256 * 1024,
                    )
                except InterruptedError:
                    self._cancel_download()
                    raise
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("FTP download cancelled.")
            actual_size = temporary.stat().st_size
            if expected_size is not None and actual_size != expected_size:
                raise IOError(
                    f"FTP download size verification failed for {remote_path}: "
                    f"expected {expected_size} bytes, got {actual_size}"
                )
            os.replace(temporary, destination)
            return "downloaded", actual_size
        except Exception:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def make_directory(self, path: str) -> None:
        raise NotImplementedError

    def rename(self, source: str, destination: str) -> None:
        raise NotImplementedError

    def delete_file(self, path: str) -> None:
        raise NotImplementedError

    def remove_directory(self, path: str) -> None:
        """Remove one empty directory only; recursive deletion is intentionally absent."""
        raise NotImplementedError

    def available_space(self) -> int | None:
        return None


class ThreeDSFtpFilesystemAdapter(_BaseFtpFilesystemAdapter):
    display_name = "Nintendo 3DS ftpd"
    capabilities = RemoteFilesystemCapabilities(resume_upload=True, free_space=True)

    def __init__(
        self,
        settings: ThreeDSFtpSettings,
        *,
        backend_factory=ThreeDSFtpBackend,
    ):
        self.settings = settings
        self.backend = backend_factory(settings)

    def connect(self) -> str:
        return self.backend.connect()

    def close(self) -> None:
        self.backend.close()

    def list_directory(self, path: str = "") -> list[RemoteEntry]:
        rows = self.backend.list_directory(path)
        entries: list[RemoteEntry] = []
        for row in rows:
            name = str(row.get("name", ""))
            if not name or name in {".", ".."}:
                continue
            kind = "dir" if str(row.get("type", "file")) == "dir" else "file"
            try:
                size = max(0, int(row.get("size", 0) or 0))
            except (TypeError, ValueError):
                size = 0
            entries.append(RemoteEntry(name, _relative_child(path, name), kind, size))
        return entries

    def upload(
        self,
        source: Path,
        remote_path: str,
        *,
        overwrite: bool = False,
        cancel_event=None,
        progress: ProgressCallback | None = None,
    ) -> tuple[str, int]:
        return self.backend.upload(
            source,
            remote_path,
            overwrite=overwrite,
            resume=True,
            cancel_event=cancel_event,
            progress=progress,
        )

    def _download_client_and_path(self, remote_path: str):
        return self.backend._require_connection(), self.backend._rooted_path(remote_path)

    def _remote_size(self, remote_path: str) -> int | None:
        return self.backend.remote_size(remote_path)

    def _cancel_download(self) -> None:
        try:
            self.backend._require_connection().abort()
        except Exception:
            pass

    def make_directory(self, path: str) -> None:
        self.backend.ensure_directory(path)

    def rename(self, source: str, destination: str) -> None:
        ftp = self.backend._require_connection()
        ftp.rename(
            self.backend._rooted_path(source),
            self.backend._rooted_path(destination),
        )

    def delete_file(self, path: str) -> None:
        ftp = self.backend._require_connection()
        ftp.delete(self.backend._rooted_path(path))

    def remove_directory(self, path: str) -> None:
        ftp = self.backend._require_connection()
        ftp.rmd(self.backend._rooted_path(path))

    def available_space(self) -> int | None:
        return self.backend.available_space()


_VITA_LIST_RE = re.compile(
    r"^(?P<kind>[d-])[rwx-]{9}\s+1\s+\S+\s+\S+\s+"
    r"(?P<size>\d+)\s+\S+\s+\d+\s+\d{2}:\d{2}\s+(?P<name>.*)$"
)


def parse_vita_list_line(line: str) -> tuple[str, str, int] | None:
    """Parse the Unix-like LIST format emitted by ftpvitalib/VitaShell."""
    match = _VITA_LIST_RE.match(line.rstrip("\r\n"))
    if match is None:
        return None
    name = match.group("name")
    if not name or name in {".", ".."}:
        return None
    kind = "dir" if match.group("kind") == "d" else "file"
    return name, kind, int(match.group("size"))


class VitaFtpFilesystemAdapter(_BaseFtpFilesystemAdapter):
    display_name = "VitaShell FTP"
    capabilities = RemoteFilesystemCapabilities(resume_upload=False, free_space=False)

    def __init__(
        self,
        settings: VitaFtpSettings,
        *,
        backend_factory=VitaFtpBackend,
    ):
        self.settings = settings
        self.backend = backend_factory(settings)

    def connect(self) -> str:
        return self.backend.connect()

    def close(self) -> None:
        self.backend.close()

    def list_directory(self, path: str = "") -> list[RemoteEntry]:
        ftp = self.backend._require_connection()
        remote = self.backend._rooted_path(path)
        lines: list[str] = []
        ftp.retrlines(f"LIST {remote}", lines.append)
        entries: list[RemoteEntry] = []
        for line in lines:
            parsed = parse_vita_list_line(line)
            if parsed is None:
                continue
            name, kind, size = parsed
            entries.append(RemoteEntry(name, _relative_child(path, name), kind, size))
        return sorted(entries, key=lambda entry: (not entry.is_dir, entry.name.casefold()))

    def upload(
        self,
        source: Path,
        remote_path: str,
        *,
        overwrite: bool = False,
        cancel_event=None,
        progress: ProgressCallback | None = None,
    ) -> tuple[str, int]:
        return self.backend.upload(
            source,
            remote_path,
            overwrite=overwrite,
            cancel_event=cancel_event,
            progress=progress,
        )

    def _download_client_and_path(self, remote_path: str):
        return self.backend._require_connection(), self.backend._rooted_path(remote_path)

    def _remote_size(self, remote_path: str) -> int | None:
        return self.backend.remote_size(remote_path)

    def _cancel_download(self) -> None:
        # ftpvitalib does not implement ABOR. Closing the control channel avoids
        # leaving ftplib desynchronised after callback interruption.
        self.backend._drop_connection()

    def make_directory(self, path: str) -> None:
        self.backend.ensure_directory(path)

    def rename(self, source: str, destination: str) -> None:
        self.backend._rename(
            self.backend._rooted_path(source),
            self.backend._rooted_path(destination),
        )

    def delete_file(self, path: str) -> None:
        ftp = self.backend._require_connection()
        self.backend._delete(ftp, self.backend._rooted_path(path))

    def remove_directory(self, path: str) -> None:
        ftp = self.backend._require_connection()
        ftp.voidcmd(f"RMD {self.backend._rooted_path(path)}")


def ftp_filesystem_for_console(
    console: str,
    settings: ThreeDSFtpSettings | VitaFtpSettings,
):
    normalized = console.strip().casefold()
    if normalized in {"3ds", "nintendo 3ds"}:
        if not isinstance(settings, ThreeDSFtpSettings):
            raise TypeError("Nintendo 3DS file manager requires ThreeDSFtpSettings.")
        return ThreeDSFtpFilesystemAdapter(settings)
    if normalized in {"vita", "ps vita", "playstation vita", "pstv", "playstation tv"}:
        if not isinstance(settings, VitaFtpSettings):
            raise TypeError("Vita file manager requires VitaFtpSettings.")
        return VitaFtpFilesystemAdapter(settings)
    raise ValueError(f"FTP file manager is not supported for console: {console}")


__all__ = [
    "RemoteEntry",
    "RemoteFilesystemCapabilities",
    "RemoteFilesystemError",
    "ThreeDSFtpFilesystemAdapter",
    "VitaFtpFilesystemAdapter",
    "ftp_filesystem_for_console",
    "parse_vita_list_line",
]
