from __future__ import annotations

import ftplib
import hashlib
import posixpath
import re
import socket
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable
from uuid import uuid4

ProgressCallback = Callable[[int], None]


@dataclass(frozen=True)
class ThreeDSFtpSettings:
    host: str
    port: int = 5000
    username: str = "anonymous"
    password: str = ""
    timeout: float = 30.0
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


def describe_connection_error(exc: BaseException) -> str:
    """Turn common 3DS FTP failures into actionable user-facing guidance."""
    detail = str(exc).strip()
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return (
            "The 3DS did not respond. Open ftpd on the console and leave it running, "
            "then confirm the PC and 3DS are on the same local network and retry."
        )
    if isinstance(exc, ConnectionRefusedError):
        return (
            "The 3DS refused the FTP connection. Open ftpd on the console and leave it "
            "running, then confirm the IP address and port shown by ftpd."
        )
    if isinstance(exc, ftplib.error_perm) and re.search(r"\b530\b", detail):
        return (
            "ftpd rejected the FTP login. Check the configured username and password, or "
            "use ftpd's default anonymous/no-password settings."
        )
    if isinstance(exc, OSError):
        return (
            "Could not reach the 3DS FTP server. Open ftpd on the console, verify the IP "
            "address and port it shows, and make sure both devices are on the same network."
            + (f" System detail: {detail}" if detail else "")
        )
    return detail or exc.__class__.__name__


class ThreeDSFtpConnectionError(ConnectionError):
    """Connection failure already translated into actionable 3DS FTP guidance."""


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

    @staticmethod
    def _close_client(ftp, *, graceful: bool = True) -> None:
        if ftp is None:
            return
        if graceful:
            try:
                ftp.quit()
                return
            except Exception:
                pass
        try:
            ftp.close()
        except Exception:
            pass

    def connect(self) -> str:
        if not self.settings.host.strip():
            raise ValueError("3DS FTP host is required.")
        ftp = self._ftp_factory(timeout=self.settings.timeout)
        try:
            ftp.connect(self.settings.host.strip(), self.settings.port, timeout=self.settings.timeout)
            ftp.login(self.settings.username or "anonymous", self.settings.password)
            ftp.set_pasv(self.settings.passive)
        except Exception as exc:
            self._close_client(ftp, graceful=False)
            raise ThreeDSFtpConnectionError(describe_connection_error(exc)) from exc

        root = normalize_remote_path(self.settings.remote_root)
        try:
            ftp.cwd(root)
            cwd = ftp.pwd()
        except Exception as exc:
            self._close_client(ftp, graceful=False)
            detail = str(exc).strip()
            raise ThreeDSFtpConnectionError(
                f"Connected to ftpd, but the configured remote root {root} is unavailable."
                + (f" Server detail: {detail}" if detail else "")
            ) from exc

        self.ftp = ftp
        return cwd

    def close(self) -> None:
        ftp, self.ftp = self.ftp, None
        self._close_client(ftp)

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
        prefix = path.rstrip("/") + "/"
        for raw_name in names:
            raw_name = str(raw_name)
            raw_candidate = normalize_remote_path(raw_name)
            if raw_name.startswith("/") or raw_candidate == path or raw_candidate.startswith(prefix):
                candidate = raw_candidate
            else:
                candidate = normalize_remote_path(posixpath.join(path, raw_name))
            if self.settings.remote_root != "/":
                root = normalize_remote_path(self.settings.remote_root)
                if candidate != root and not candidate.startswith(root.rstrip("/") + "/"):
                    continue
            name = candidate.rstrip("/").split("/")[-1] or candidate
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

    @staticmethod
    def _rest_not_supported(exc: BaseException) -> bool:
        """Return True for standard FTP responses rejecting the REST command."""
        return bool(re.search(r"\b(?:500|501|502|504)\b", str(exc).upper()))

    @staticmethod
    def _source_digest(local_path: Path, cancel_event=None) -> str:
        hasher = hashlib.sha256()
        with local_path.open("rb") as source:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise InterruptedError("Transfer cancelled.")
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def _staging_path(remote: str, source_digest: str) -> str:
        parent = posixpath.dirname(remote)
        remote_tag = hashlib.sha256(remote.encode("utf-8")).hexdigest()[:12]
        name = f".rommheld-{source_digest[:24]}-{remote_tag}.part"
        return posixpath.join(parent, name)

    @staticmethod
    def _backup_path(remote: str) -> str:
        parent = posixpath.dirname(remote)
        return posixpath.join(parent, f".rommheld-{uuid4().hex}.bak")

    @staticmethod
    def _delete(ftp, remote: str) -> None:
        ftp.delete(remote)

    @staticmethod
    def _rename(ftp, source: str, destination: str) -> None:
        ftp.rename(source, destination)

    def _delete_if_present(self, ftp, remote: str) -> None:
        try:
            self._delete(ftp, remote)
        except (ftplib.error_perm, ftplib.error_reply):
            pass

    def _restore_backup(self, ftp, backup: str | None, remote: str) -> None:
        if backup is None:
            self._delete_if_present(ftp, remote)
            return
        self._delete_if_present(ftp, remote)
        self._rename(ftp, backup, remote)

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
        """Upload through a verified staging file, resuming only matching RommHeld stages."""
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
        if remote_existing is not None and not overwrite:
            return "different", 0
        if cancel_event is not None and cancel_event.is_set():
            return "cancelled", 0

        try:
            source_digest = self._source_digest(local_path, cancel_event)
        except InterruptedError:
            return "cancelled", 0

        temporary = self._staging_path(remote, source_digest)
        try:
            temp_existing = ftp.size(temporary)
            temp_existing = int(temp_existing) if temp_existing is not None else None
        except (ftplib.error_perm, ftplib.error_reply):
            temp_existing = None

        offset = 0
        if resume and temp_existing is not None and 0 < temp_existing < source_size:
            offset = temp_existing
        elif temp_existing == source_size:
            if progress is not None:
                progress(source_size)
            offset = source_size
        elif temp_existing is not None and temp_existing > source_size:
            self._delete_if_present(ftp, temporary)

        transferred = offset
        did_resume = bool(offset)
        blocksize = 256 * 1024

        if offset != source_size:
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

                try:
                    ftp.storbinary(
                        f"STOR {temporary}",
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
                except (ftplib.error_perm, ftplib.error_reply) as exc:
                    if not offset or not self._rest_not_supported(exc):
                        raise
                    src.seek(0)
                    transferred = 0
                    did_resume = False
                    if progress is not None:
                        progress(0)
                    try:
                        ftp.storbinary(
                            f"STOR {temporary}",
                            src,
                            blocksize=blocksize,
                            callback=callback,
                        )
                    except InterruptedError:
                        try:
                            ftp.abort()
                        except Exception:
                            pass
                        return "cancelled", transferred

        try:
            temp_size = ftp.size(temporary)
            temp_size = int(temp_size) if temp_size is not None else None
        except (ftplib.error_perm, ftplib.error_reply):
            temp_size = None
        if temp_size != source_size:
            raise IOError(
                f"FTP size verification failed for staged upload {temporary}: expected {source_size} bytes, got {temp_size}"
            )

        backup = None
        if remote_existing is not None:
            backup = self._backup_path(remote)
            self._rename(ftp, remote, backup)

        try:
            self._rename(ftp, temporary, remote)
        except Exception:
            if backup is not None:
                self._restore_backup(ftp, backup, remote)
            raise

        final_size = self.remote_size(remote_path)
        if final_size != source_size:
            try:
                self._restore_backup(ftp, backup, remote)
            finally:
                if backup is None:
                    self._delete_if_present(ftp, remote)
            raise IOError(
                f"FTP size verification failed for {remote}: expected {source_size} bytes, got {final_size}"
            )

        if backup is not None:
            try:
                self._delete(ftp, backup)
            except Exception:
                pass
        return ("resumed" if did_resume else "copied"), source_size
