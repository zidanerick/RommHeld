from __future__ import annotations

import ftplib
from dataclasses import replace
from typing import Callable

from .three_ds_apps import THREE_DS_APPS, ThreeDSAppStatus
from .three_ds_ftp import ThreeDSFtpBackend, ThreeDSFtpSettings


CancelCheck = Callable[[], bool]


def _is_hex_name(value: str, length: int) -> bool:
    return len(value) == length and all(ch in "0123456789abcdefABCDEF" for ch in value)


class _RemoteTree:
    def __init__(self, backend: ThreeDSFtpBackend, cancelled: CancelCheck | None = None):
        self.backend = backend
        self.cancelled = cancelled
        self._cache: dict[str, tuple[dict[str, str | int], ...]] = {}

    def _check_cancelled(self) -> None:
        if self.cancelled is not None and self.cancelled():
            raise InterruptedError("FTP readiness scan cancelled.")

    def list(self, path: str = "") -> tuple[dict[str, str | int], ...]:
        self._check_cancelled()
        key = path.strip("/")
        if key not in self._cache:
            try:
                rows = self.backend.list_directory(key)
            except (ftplib.error_perm, ftplib.error_reply):
                rows = []
            self._cache[key] = tuple(rows)
        return self._cache[key]

    def resolve_entry(self, marker: str) -> tuple[str, dict[str, str | int]] | None:
        current = ""
        actual_parts: list[str] = []
        final_entry: dict[str, str | int] | None = None
        for raw_part in marker.replace("\\", "/").split("/"):
            part = raw_part.strip()
            if not part or part == ".":
                continue
            match = next(
                (
                    row
                    for row in self.list(current)
                    if str(row.get("name", "")).casefold() == part.casefold()
                ),
                None,
            )
            if match is None:
                return None
            actual = str(match.get("name", ""))
            actual_parts.append(actual)
            current = "/".join(actual_parts)
            final_entry = match
        if final_entry is None:
            return None
        return current, final_entry

    def resolve(self, marker: str) -> str | None:
        resolved = self.resolve_entry(marker)
        return resolved[0] if resolved is not None else None

    def marker_present(self, marker: str) -> bool:
        resolved = self.resolve_entry(marker)
        if resolved is None:
            return False
        _path, entry = resolved
        if entry.get("type") != "file":
            return True
        try:
            return int(entry.get("size", 0)) > 0
        except (TypeError, ValueError):
            return False


def _remote_title_roots(tree: _RemoteTree) -> tuple[str, ...]:
    base = tree.resolve("Nintendo 3DS")
    if base is None:
        return ()

    roots: list[str] = []
    for id0 in tree.list(base):
        id0_name = str(id0.get("name", ""))
        if id0.get("type") != "dir" or not _is_hex_name(id0_name, 32):
            continue
        id0_path = f"{base}/{id0_name}"
        for id1 in tree.list(id0_path):
            id1_name = str(id1.get("name", ""))
            if id1.get("type") != "dir" or not _is_hex_name(id1_name, 32):
                continue
            title_root = tree.resolve(f"{id0_path}/{id1_name}/title")
            if title_root is not None:
                roots.append(title_root)
    return tuple(roots)


def _remote_title_present(tree: _RemoteTree, title_roots: tuple[str, ...], title_id: str) -> bool:
    high, low = title_id[:8], title_id[8:]
    return any(tree.resolve(f"{root}/{high}/{low}") is not None for root in title_roots)


def scan_three_ds_apps_ftp(
    settings: ThreeDSFtpSettings,
    *,
    backend_factory=ThreeDSFtpBackend,
    cancelled: CancelCheck | None = None,
) -> dict[str, ThreeDSAppStatus]:
    """Inspect runtime/homebrew evidence through a live 3DS ftpd connection.

    The scan reuses the declarative marker and known-title rules from
    ``three_ds_apps``. It does not decrypt title databases or infer installed
    CIA state from unrelated files. A successful connection itself is reliable
    evidence that ftpd is currently available.
    """

    scan_settings = replace(settings, timeout=min(float(settings.timeout), 8.0))
    backend = backend_factory(scan_settings)
    try:
        backend.connect()
        tree = _RemoteTree(backend, cancelled)
        title_roots = _remote_title_roots(tree)
        statuses: dict[str, ThreeDSAppStatus] = {}

        for definition in THREE_DS_APPS:
            if cancelled is not None and cancelled():
                raise InterruptedError("FTP readiness scan cancelled.")

            if definition.key == "ftpd":
                statuses[definition.key] = ThreeDSAppStatus(
                    definition,
                    True,
                    marker="live ftpd connection",
                    source="ftp_live",
                )
                continue

            found_title_id = None
            for raw_title_id in definition.installed_title_ids:
                normalized = raw_title_id.strip().upper()
                if _remote_title_present(tree, title_roots, normalized):
                    found_title_id = normalized
                    break

            if found_title_id is not None:
                statuses[definition.key] = ThreeDSAppStatus(
                    definition,
                    True,
                    marker=(
                        "Nintendo 3DS/<ID0>/<ID1>/title/"
                        f"{found_title_id[:8]}/{found_title_id[8:]}"
                    ),
                    title_id=found_title_id,
                    source="ftp",
                )
                continue

            matched = tuple(
                marker for marker in definition.markers if tree.marker_present(marker)
            )
            marker_match = (
                len(matched) == len(definition.markers)
                if definition.marker_policy == "all"
                else bool(matched)
            )
            marker = "; ".join(matched) if marker_match and matched else None
            if marker_match and definition.marker_confirms_launchable:
                statuses[definition.key] = ThreeDSAppStatus(
                    definition,
                    True,
                    marker=marker,
                    source="ftp",
                )
            else:
                statuses[definition.key] = ThreeDSAppStatus(
                    definition,
                    False,
                    marker=marker,
                    source="ftp",
                )
        return statuses
    finally:
        backend.close()


def merge_three_ds_app_inventories(
    *inventories: dict[str, ThreeDSAppStatus],
) -> dict[str, ThreeDSAppStatus]:
    """Prefer the strongest positive evidence, then preserve useful file evidence."""

    result: dict[str, ThreeDSAppStatus] = {}
    for definition in THREE_DS_APPS:
        candidates = [inventory.get(definition.key) for inventory in inventories]
        detected_candidates = [status for status in candidates if status and status.detected]
        detected = next(
            (status for status in detected_candidates if status.title_id),
            detected_candidates[0] if detected_candidates else None,
        )
        if detected is not None:
            result[definition.key] = detected
            continue
        evidence = next(
            (status for status in reversed(candidates) if status is not None and status.marker),
            None,
        )
        fallback = evidence or next(
            (status for status in reversed(candidates) if status is not None),
            None,
        )
        result[definition.key] = fallback or ThreeDSAppStatus(
            definition,
            False,
            source="unchecked",
        )
    return result


__all__ = ["merge_three_ds_app_inventories", "scan_three_ds_apps_ftp"]
