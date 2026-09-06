from __future__ import annotations

import ftplib
import posixpath
import re
import socket
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable
from uuid import uuid4

ProgressCallback = Callable[[int], None]
_VOLUME_PATH_RE = re.compile(r"^/?[A-Za-z0-9_]+:(?:/|$)")


@dataclass(frozen=True)
class VitaFtpSettings:
    host: str
    port: int = 1337
    username: str = "anonymous"
    password: str = ""
    timeout: float = 30.0
    passive: bool = True
    remote_root: str = "/ux0:"


def normalize_vita_ftp_path(path: str) -> str:
    """Normalize VitaShell's Unix-like FTP paths and reject traversal."""
    raw = path.strip().replace("\\", "/")
    if not raw:
        return "/"
    if _VOLUME_PATH_RE.match(raw):
        raw = "/" + raw.lstrip("/")
    parts = [part for part in PurePosixPath(raw).parts if part not in {".", "", "/"}]
    if any(part == ".." for part in parts):
        raise ValueError(f"Vita FTP path traversal is not allowed: {path}")
    normalized = posixpath.normpath("/" + "/".join(parts))
    return normalized if normalized.startswith("/") else "/" + normalized


def join_vita_ftp_path(root: str, child: str) -> str:
    """Resolve a path beneath the configured VitaShell FTP mountpoint."""
    root_path = normalize_vita_ftp_path(root)
    child_raw = child.strip().replace("\\", "/")
    if not child_raw:
        return root_path
    if _VOLUME_PATH_RE.match(child_raw) or child_raw.startswith("/"):
        target = normalize_vita_ftp_path(child_raw)
    else:
        target = normalize_vita_ftp_path(posixpath.join(root_path, child_raw))
    if root_path != "/" and target != root_path and not target.startswith(root_path.rstrip("/") + "/"):
        raise ValueError(f"Vita FTP path escapes configured root: {child}")
    return target


def describe_vita_ftp_connection_error(exc: BaseException) -> str:
    detail = str(exc).strip()
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return (
            "The Vita did not respond. In VitaShell press START, set SELECT button to FTP, "
            "close Settings and press SELECT. Enter the IP address and port shown by VitaShell, "
            "then confirm the Vita and PC are on the same local network."
        )
    if isinstance(exc, ConnectionRefusedError):
        return (
            "The Vita refused the FTP connection. Start FTP in VitaShell by pressing SELECT, "
            "then confirm the IP address and port shown on the VitaShell screen."
        )
    if isinstance(exc, OSError):
        return (
            "Could not reach VitaShell FTP. Start FTP with SELECT in VitaShell, verify the IP "
            "address and port it shows, and make sure the Vita and PC are on the same network."
            + (f" System detail: {detail}" if detail else "")
        )
    return detail or exc.__class__.__name__


class VitaFtpConnectionError(ConnectionError):
    """Connection failure already translated into actionable VitaShell guidance."""


class VitaFtpBackend:
    """FTP transport matched to VitaShell/ftpvitalib semantics."""

    def __init__(self, settings: VitaFtpSettings, ftp_factory=ftplib.FTP):
        self.settings = settings
        self._ftp_factory = ftp_factory
        self.ftp = None

    @property
    def connected(self) -> bool:
        return self.ftp is not None

    def _rooted_path(self, path: str) -> str:
        return join_vita_ftp_path(self.settings.remote_root, path)

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

    def _new_client(self):
        if not self.settings.host.strip():
            raise ValueError("Vita FTP host is required.")
        ftp = self._ftp_factory(timeout=self.settings.timeout)
        try:
            ftp.connect(self.settings.host.strip(), self.settings.port, timeout=self.settings.timeout)
            ftp.login(self.settings.username or "anonymous", self.settings.password)
            ftp.set_pasv(self.settings.passive)
            ftp.cwd(normalize_vita_ftp_path(self.settings.remote_root))
        except Exception as exc:
            self._close_client(ftp, graceful=False)
            raise VitaFtpConnectionError(describe_vita_ftp_connection_error(exc)) from exc
        return ftp

    def connect(self) -> str:
        ftp = self._new_client()
        self.ftp = ftp
        return ftp.pwd()

    def close(self) -> None:
        ftp, self.ftp = self.ftp, None
        self._close_client(ftp)

    def _drop_connection(self) -> None:
        ftp, self.ftp = self.ftp, None
        self._close_client(ftp, graceful=False)

    def _require_connection(self):
        if self.ftp is None:
            raise RuntimeError("VitaShell FTP is not connected.")
        return self.ftp

    def remote_size(self, path: str) -> int | None:
        ftp = self._require_connection()
        remote = self._rooted_path(path)
        try:
            response = ftp.sendcmd(f"SIZE {remote}")
        except (ftplib.error_perm, ftplib.error_reply):
            return None
        values = re.findall(r"\d+", response or "")
        return int(values[-1]) if values else None

    def ensure_directory(self, path: str) -> None:
        ftp = self._require_connection()
        target = self._rooted_path(path)
        root = normalize_vita_ftp_path(self.settings.remote_root)
        if target == root:
            return
        if not target.startswith(root.rstrip("/") + "/"):
            raise ValueError(f"Vita FTP directory escapes configured root: {path}")

        current = root
        for part in target[len(root):].strip("/").split("/"):
            if not part:
                continue
            current = current.rstrip("/") + "/" + part
            try:
                ftp.cwd(current)
            except ftplib.error_perm:
                ftp.voidcmd(f"MKD {current}")
                ftp.cwd(current)

    def _delete(self, ftp, remote: str) -> None:
        ftp.voidcmd(f"DELE {remote}")

    def _cleanup_remote_file(self, remote: str) -> None:
        client = None
        try:
            client = self._new_client()
            self._delete(client, remote)
        except Exception:
            pass
        finally:
            self._close_client(client)

    def _rename(self, source: str, destination: str) -> None:
        ftp = self._require_connection()
        ftp.sendcmd(f"RNFR {source}")
        ftp.voidcmd(f"RNTO {destination}")

    def _restore_backup(self, backup: str | None, remote: str) -> None:
        ftp = self._require_connection()
        if backup is None:
            try:
                if self.remote_size(remote) is not None:
                    self._delete(ftp, remote)
            except Exception:
                pass
            return
        try:
            if self.remote_size(remote) is not None:
                self._delete(ftp, remote)
        except Exception:
            pass
        self._rename(backup, remote)

    def _recover_failed_backup_rename(self, backup: str, remote: str) -> None:
        """Best-effort recovery when RNTO fails after a destination backup attempt."""
        try:
            remote_present = self.remote_size(remote) is not None
            backup_present = self.remote_size(backup) is not None
            if not remote_present and backup_present:
                self._rename(backup, remote)
        except Exception:
            # Preserve the original rename failure. If VitaShell left a backup in
            # place, it is safer to retain that recovery copy than mask the cause.
            pass

    def upload(
        self,
        local_path: Path,
        remote_path: str,
        *,
        overwrite: bool = False,
        cancel_event=None,
        progress: ProgressCallback | None = None,
    ) -> tuple[str, int]:
        """Upload safely without REST; verify a temporary file before replacing the destination."""
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

        parent = posixpath.dirname(remote)
        token = uuid4().hex
        temporary = posixpath.join(
            parent, f".{posixpath.basename(remote)}.rommheld-{token}.part"
        )
        transferred = 0

        def callback(chunk: bytes) -> None:
            nonlocal transferred
            transferred += len(chunk)
            if progress is not None:
                progress(transferred)
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("Transfer cancelled.")

        try:
            with local_path.open("rb") as src:
                ftp.storbinary(
                    f"STOR {temporary}",
                    src,
                    blocksize=256 * 1024,
                    callback=callback,
                )
        except InterruptedError:
            # VitaShell does not implement ABOR. Drop the desynchronised control
            # connection, then remove the temporary file through a fresh session.
            self._drop_connection()
            self._cleanup_remote_file(temporary)
            return "cancelled", transferred
        except Exception:
            self._drop_connection()
            self._cleanup_remote_file(temporary)
            raise

        if cancel_event is not None and cancel_event.is_set():
            self._cleanup_remote_file(temporary)
            return "cancelled", transferred

        try:
            temp_size = self.remote_size(temporary)
        except Exception:
            # A successful STOR can still be followed by a dead control connection.
            # Fail closed before any destination swap and clean the verified-staging
            # candidate through a fresh VitaShell FTP session when possible.
            self._drop_connection()
            self._cleanup_remote_file(temporary)
            raise
        if temp_size != source_size:
            self._cleanup_remote_file(temporary)
            raise IOError(
                f"Vita FTP size verification failed for temporary upload: expected {source_size} bytes, got {temp_size}"
            )

        backup = None
        if remote_existing is not None:
            backup = posixpath.join(
                parent, f".{posixpath.basename(remote)}.rommheld-{token}.backup"
            )
            try:
                self._rename(remote, backup)
            except Exception:
                self._recover_failed_backup_rename(backup, remote)
                self._cleanup_remote_file(temporary)
                raise

        try:
            self._rename(temporary, remote)
        except Exception:
            try:
                self._restore_backup(backup, remote)
            finally:
                self._cleanup_remote_file(temporary)
            raise

        try:
            final_size = self.remote_size(remote)
        except Exception as verification_error:
            # The temporary upload was already size-verified before the rename. If
            # only the control connection died during final verification, reconnect
            # once so a healthy completed transfer can remain successful and the
            # worker can continue its batch.
            self._drop_connection()
            try:
                self.ftp = self._new_client()
                final_size = self.remote_size(remote)
            except Exception:
                self._drop_connection()
                raise verification_error
        if final_size != source_size:
            try:
                self._restore_backup(backup, remote)
            finally:
                self._cleanup_remote_file(temporary)
            raise IOError(
                f"Vita FTP size verification failed for {remote}: expected {source_size} bytes, got {final_size}"
            )

        if backup is not None:
            try:
                self._delete(self._require_connection(), backup)
            except Exception:
                # The replacement is already verified and live. A stale hidden
                # backup is preferable to reporting the successful transfer as failed.
                pass
        return "copied", source_size


__all__ = [
    "VitaFtpBackend",
    "VitaFtpConnectionError",
    "VitaFtpSettings",
    "describe_vita_ftp_connection_error",
    "join_vita_ftp_path",
    "normalize_vita_ftp_path",
]
