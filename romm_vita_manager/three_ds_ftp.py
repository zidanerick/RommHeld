from __future__ import annotations

import ftplib
import posixpath
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Callable

ProgressCallback = Callable[[int], None]


@dataclass(frozen=True)
class ThreeDSFtpSettings:
    host: str
    port: int = 5000
    username: str = "anonymous"
    password: str = ""
    timeout: float = 8.0
    passive: bool = True
    remote_root: str = "/"


def normalize_remote_path(path: str) -> str:
    """Normalize an FTP path and reject traversal components."""
    raw = path.strip().replace("\\", "/")
    if not raw:
        return "/"
    if raw == "/":
        return "/"
    parts = [part for part in PurePosixPath(raw).parts if part not in {".", "", "/"}]
    if any(part == ".." for part in parts):
        raise ValueError(f"Remote path traversal is not allowed: {path}")
    normalized = posixpath.normpath("/" + "/".join(parts))
    return normalized if normalized.startswith("/") else "/" + normalized


def join_remote_path(root: str, child: str) -> str:
    """Join a child path under a configured FTP root."""
    root_path = normalize_remote_path(root)
    child_raw = child.strip().replace("\\", "/")
    if not child_raw:
        return root_path
    if child_raw.startswith("/"):
        target = normalize_remote_path(child_raw)
    else:
        target = normalize_remote_path(posixpath.join(root_path, child_raw))
    if root_path != "/" and target != root_path and not target.startswith(root_path.rstrip("/") + "/"):
        raise ValueError(f"Remote path escapes configured root: {child}")
    return target


class ThreeDSFtpBackend:
    """FTP transport for a Nintendo 3DS FTP server."""

    def __init__(self, settings: ThreeDSFtpSettings, ftp_factory=ftplib.FTP):
        self.settings = settings
        self._ftp_factory = ftp_factory
        self.ftp = None

    @property
    def connected(self) -> bool:
        return self.ftp is not None

    def _rooted_path(self, path: str) -> str:
        """Resolve a path under the configured remote root."""
        return join_remote_path(self.settings.remote_root, path)

    def connect(self) -> str:
        if not self.settings.host.strip():
            raise ValueError("3DS FTP host is required.")
        ftp = self._ftp_factory(timeout=self.settings.timeout)
        ftp.connect(self.settings.host.strip(), self.settings.port, timeout=self.settings.timeout)
        ftp.login(self.settings.username or "anonymous", self.settings.password)
        ftp.set_pasv(self.settings.passive)
        self.ftp = ftp
        return ftp.pwd()

    def close(self) -> None:
        ftp, self.ftp = self.ftp, None
        if ftp is None:
            return
        try:
            ftp.quit()
        except Exception:
            try:
                ftp.close()
            except Exception:
                pass

    def _require_connection(self):
        if self.ftp is None:
            raise RuntimeError("3DS FTP is not connected.")
        return self.ftp

    def list_directory(self, path: str = "") -> list[dict[str, str | int]]:
        ftp = self._require_connection()
        normalized = self._rooted_path(path)
        try:
            rows: list[dict[str, str | int]] = []
            for name, facts in ftp.mlsd(normalized):
                item_type = str(facts.get("type", "file"))
                size_text = facts.get("size")
                size = int(size_text) if isinstance(size_text, str) and size_text.isdigit() else 0
                rows.append({"name": name, "type": item_type, "size": size})
            return sorted(rows, key=lambda item: (item["type"] != "dir", str(item["name"]).lower()))
        except (AttributeError, ftplib.error_perm):
            return self._list_directory_fallback(normalized)

    def _list_directory_fallback(self, path: str) -> list[dict[str, str | int]]:
        ftp = self._require_connection()
        names = ftp.nlst(path)
        result: list[dict[str, str | int]] = []
        for raw_name in names:
            raw_name = str(raw_name)
            name = raw_name.rstrip("/").split("/")[-1] or raw_name
            candidate = normalize_remote_path(raw_name)
            if self.settings.remote_root != "/":
                root = normalize_remote_path(self.settings.remote_root)
                if candidate != root and not candidate.startswith(root.rstrip("/") + "/"):
                    continue
            is_dir = False
            current = ftp.pwd()
            try:
                ftp.cwd(candidate)
                is_dir = True
            except Exception:
                pass
            finally:
                try:
                    ftp.cwd(current)
                except Exception:
                    pass
            size = 0
            if not is_dir:
                try:
                    value = ftp.size(candidate)
                    size = int(value or 0)
                except Exception:
                    pass
            result.append({"name": name, "type": "dir" if is_dir else "file", "size": size})
        return sorted(result, key=lambda item: (item["type"] != "dir", str(item["name"]).lower()))

    def remote_size(self, path: str) -> int | None:
        ftp = self._require_connection()
        normalized = self._rooted_path(path)
        try:
            value = ftp.size(normalized)
            return int(value) if value is not None else None
        except (ftplib.error_perm, ftplib.error_reply):
            return None

    def available_space(self) -> int | None:
        """Best effort support for servers implementing SITE AVBL."""
        ftp = self._require_connection()
        try:
            response = ftp.sendcmd("SITE AVBL")
        except Exception:
            return None
        values = re.findall(r"\d+", response or "")
        return int(values[-1]) if values else None

    def ensure_directory(self, path: str) -> None:
        ftp = self._require_connection()
        target = self._rooted_path(path)
        if target == "/":
            return
        current = ftp.pwd()
        try:
            ftp.cwd("/")
            for part in target.strip("/").split("/"):
                try:
                    ftp.cwd(part)
                except ftplib.error_perm:
                    ftp.mkd(part)
                    ftp.cwd(part)
        finally:
            try:
                ftp.cwd(current)
            except Exception:
                pass

    def upload(
        self,
        local_path,
        remote_path: str,
        *,
        overwrite: bool = False,
        resume: bool = True,
        cancel_event=None,
        progress: ProgressCallback | None = None,
    ) -> tuple[str, int]:
        """Upload a local file using FTP, returning status and bytes transferred."""
        ftp = self._require_connection()
        local_path = local_path.expanduser()
        if not local_path.is_file():
            raise FileNotFoundError(f"Source file does not exist: {local_path}")

        remote = self._rooted_path(remote_path)
        self.ensure_directory(posixpath.dirname(remote))
        source_size = local_path.stat().st_size
        remote_existing = self.remote_size(remote_path)

        if remote_existing == source_size:
            return "skipped", source_size
        if remote_existing is not None and remote_existing > source_size and not overwrite:
            return "different", 0
        if remote_existing is not None and remote_existing not in (0, source_size) and not overwrite and not (resume and remote_existing < source_size):
            return "different", 0

        offset = remote_existing if resume and remote_existing and remote_existing < source_size else 0
        transferred = offset
        blocksize = 256 * 1024

        try:
            with local_path.open("rb") as src:
                if offset:
                    src.seek(offset)

                def callback(chunk: bytes) -> None:
                    nonlocal transferred
                    transferred += len(chunk)
                    if progress is not None:
                        progress(transferred)
                    if cancel_event is not None and cancel_event.is_set():
                        raise InterruptedError("Transfer cancelled.")

                ftp.storbinary(
                    f"STOR {remote}",
                    src,
                    blocksize=blocksize,
                    callback=callback,
                    rest=offset or None,
                )
        except InterruptedError:
            try:
                ftp.abort()
            except Exception:
                pass
            return "cancelled", transferred

        final_size = self.remote_size(remote_path)
        if final_size != source_size:
            raise IOError(
                f"FTP size verification failed for {remote}: expected {source_size} bytes, got {final_size}"
            )
        return ("resumed" if offset else "copied"), source_size
