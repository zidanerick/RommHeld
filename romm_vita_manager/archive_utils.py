from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import tarfile
import zipfile


@dataclass(frozen=True)
class ArchiveEntry:
    name: str
    size: int
    is_directory: bool


def list_archive(archive: Path) -> list[ArchiveEntry]:
    """Return archive members without extracting anything."""
    suffix = archive.suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            return [
                ArchiveEntry(info.filename, info.file_size, info.is_dir())
                for info in zf.infolist()
            ]
    if suffix in {".tar", ".tgz", ".gz", ".bz2", ".xz"} or archive.name.endswith(".tar.gz"):
        with tarfile.open(archive, "r:*") as tf:
            return [
                ArchiveEntry(member.name, member.size, member.isdir())
                for member in tf.getmembers()
            ]
    raise ValueError(f"Unsupported archive format: {archive.name}")


def _safe_member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe archive member path: {name}")
    return path


def _match_prefix(name: str, prefix: str | None) -> str | None:
    if not prefix:
        return name
    clean = prefix.strip("/")
    if name == clean or name.startswith(clean + "/"):
        return name
    return None


def extract_archive(
    archive: Path,
    destination: Path,
    *,
    source_prefix: str | None = None,
) -> list[Path]:
    """Safely extract an archive, optionally stripping a known source prefix."""
    destination = destination.resolve()
    written: list[Path] = []
    suffix = archive.suffix.lower()

    def target_for(name: str) -> Path | None:
        matched = _match_prefix(name, source_prefix)
        if matched is None:
            return None
        if source_prefix:
            matched = matched[len(source_prefix.strip("/")) :].lstrip("/")
        relative = _safe_member_path(matched)
        target = (destination / Path(*relative.parts)).resolve()
        if destination != target and destination not in target.parents:
            raise ValueError(f"Archive member escapes destination: {name}")
        return target

    if suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                target = target_for(info.filename)
                if target is None:
                    continue
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as source, target.open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
                written.append(target)
        return written

    if suffix in {".tar", ".tgz", ".gz", ".bz2", ".xz"} or archive.name.endswith(".tar.gz"):
        with tarfile.open(archive, "r:*") as tf:
            for member in tf.getmembers():
                target = target_for(member.name)
                if target is None:
                    continue
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    raise ValueError(f"Unsupported archive member type: {member.name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                source = tf.extractfile(member)
                if source is None:
                    raise IOError(f"Unable to read archive member: {member.name}")
                with source, target.open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
                written.append(target)
        return written

    raise ValueError(f"Unsupported archive format: {archive.name}")
