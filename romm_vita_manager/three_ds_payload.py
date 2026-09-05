from __future__ import annotations

from pathlib import Path
import tempfile

from .archive_utils import extract_archive
from .romm_remote import RomMRemoteGame, download_rom


# Targets that require a raw runtime payload rather than an archive/container.
# RetroArch is intentionally absent because individual libretro cores may accept
# compressed content directly and that policy belongs to the selected core.
_RAW_PAYLOAD_SUFFIXES: dict[tuple[str, str], frozenset[str]] = {
    ("open_agb_firm", "gba"): frozenset({".gba"}),
    ("native_gba", "gba"): frozenset({".gba"}),
    ("twilight", "nds"): frozenset({".nds"}),
    ("red_viper", "virtualboy"): frozenset({".vb"}),
    ("daedalusx64", "n64"): frozenset({".n64", ".v64", ".z64"}),
    ("vc_cia", "gba"): frozenset({".gba"}),
    ("vc_cia", "gb"): frozenset({".gb"}),
    ("vc_cia", "gbc"): frozenset({".gbc"}),
    ("vc_cia", "nes"): frozenset({".nes"}),
    ("vc_cia", "gamegear"): frozenset({".gg"}),
    ("vc_cia", "snes"): frozenset({".sfc", ".smc"}),
}

_ARCHIVE_SUFFIXES = frozenset({
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".tgz",
    ".gz",
    ".bz2",
    ".xz",
})
_EXTRACTABLE_ARCHIVE_SUFFIXES = frozenset({
    ".zip",
    ".tar",
    ".tgz",
    ".gz",
    ".bz2",
    ".xz",
})


def expected_payload_suffixes(target_key: str, platform_slug: str) -> frozenset[str] | None:
    return _RAW_PAYLOAD_SUFFIXES.get((target_key.lower(), platform_slug.lower()))


def archive_suffix(filename: str) -> str | None:
    name = Path(str(filename or "").replace("\\", "/")).name.casefold()
    if name.endswith(".tar.gz"):
        return ".gz"
    suffix = Path(name).suffix.casefold()
    return suffix if suffix in _ARCHIVE_SUFFIXES else None


def requires_payload_resolution(target_key: str, platform_slug: str, filename: str) -> bool:
    return (
        expected_payload_suffixes(target_key, platform_slug) is not None
        and archive_suffix(filename) is not None
    )


def raw_payload_supported_for_file(target_key: str, platform_slug: str, filename: str) -> bool:
    """Return whether RommHeld can safely prepare the supplied payload for this target."""
    expected = expected_payload_suffixes(target_key, platform_slug)
    if expected is None:
        return True
    suffix = Path(str(filename or "").replace("\\", "/")).suffix.casefold()
    if suffix in expected:
        return True
    archive = archive_suffix(filename)
    return archive in _EXTRACTABLE_ARCHIVE_SUFFIXES


def _archive_stem(filename: str) -> str:
    name = Path(str(filename or "").replace("\\", "/")).name
    lowered = name.casefold()
    if lowered.endswith(".tar.gz"):
        return name[:-7]
    return Path(name).stem


def planned_payload_filename(target_key: str, platform_slug: str, filename: str) -> str | None:
    """Return a deterministic destination filename when it can be known pre-extraction."""
    expected = expected_payload_suffixes(target_key, platform_slug)
    name = Path(str(filename or "").replace("\\", "/")).name
    if expected is None:
        return name
    suffix = Path(name).suffix.casefold()
    if suffix in expected:
        return name
    archive = archive_suffix(name)
    if archive not in _EXTRACTABLE_ARCHIVE_SUFFIXES:
        return None
    if len(expected) == 1:
        return f"{_archive_stem(name)}{next(iter(expected))}"
    return None


def resolve_target_payload(
    source: Path,
    target_key: str,
    platform_slug: str,
    workspace: Path,
) -> Path:
    """Return a runtime-ready payload, extracting one unambiguous ROM when required."""
    source = source.expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"Source file does not exist: {source}")

    expected = expected_payload_suffixes(target_key, platform_slug)
    if expected is None:
        return source

    suffix = source.suffix.casefold()
    if suffix in expected:
        return source

    archive = archive_suffix(source.name)
    if archive is None:
        wanted = ", ".join(sorted(expected))
        raise ValueError(
            f"{target_key} requires a raw {platform_slug} payload ({wanted}); "
            f"{source.name!r} is not compatible."
        )
    if archive not in _EXTRACTABLE_ARCHIVE_SUFFIXES:
        raise ValueError(
            f"{source.suffix or archive} archives cannot yet be safely extracted for "
            f"the {target_key} route. Extract the ROM first or choose a compatible route."
        )

    extraction_root = workspace / "extracted"
    extraction_root.mkdir(parents=True, exist_ok=True)
    written = extract_archive(source, extraction_root)
    candidates = sorted(
        (
            path
            for path in written
            if path.is_file() and path.suffix.casefold() in expected
        ),
        key=lambda path: str(path).casefold(),
    )
    if not candidates:
        wanted = ", ".join(sorted(expected))
        raise ValueError(
            f"{source.name!r} does not contain a compatible {platform_slug} ROM ({wanted})."
        )
    if len(candidates) != 1:
        names = ", ".join(path.name for path in candidates[:5])
        suffix_text = "…" if len(candidates) > 5 else ""
        raise ValueError(
            f"{source.name!r} contains multiple compatible ROM payloads ({names}{suffix_text}). "
            "RommHeld will not guess which one to deploy."
        )
    return candidates[0]


def download_target_payload(
    instance_url: str,
    token: str,
    game: RomMRemoteGame,
    target_key: str,
    platform_slug: str,
    workspace: Path,
    *,
    cancel_event=None,
    progress=None,
) -> Path:
    """Download a RomM item and resolve it to the payload required by the target."""
    filename = Path(game.filename.replace("\\", "/")).name or f"rom-{game.rom_id}"
    download_root = workspace / "download"
    download_root.mkdir(parents=True, exist_ok=True)
    download_path = download_root / filename
    download_rom(
        instance_url,
        token,
        game,
        download_path,
        cancel_event=cancel_event,
        progress=progress,
    )
    return resolve_target_payload(download_path, target_key, platform_slug, workspace)


def temporary_payload_workspace(prefix: str = "rommheld-3ds-payload-"):
    """Small helper kept here so payload callers share the same cleanup pattern."""
    return tempfile.TemporaryDirectory(prefix=prefix)


__all__ = [
    "archive_suffix",
    "download_target_payload",
    "expected_payload_suffixes",
    "planned_payload_filename",
    "raw_payload_supported_for_file",
    "requires_payload_resolution",
    "resolve_target_payload",
    "temporary_payload_workspace",
]
