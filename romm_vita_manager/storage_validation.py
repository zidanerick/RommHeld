from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StorageValidation:
    kind: str
    confidence: str
    signatures: tuple[str, ...]


def validate_storage(root: Path) -> StorageValidation:
    """Perform a read-only heuristic validation of a mounted handheld storage root."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Storage root does not exist: {root}")

    names = {entry.name.lower() for entry in root.iterdir()}
    signatures: list[str] = []

    has_3ds = {"boot.firm", "boot.3dsx", "luma", "gm9"}.issubset(names)
    has_twilight = "_nds" in names or ("boot.nds" in names and "roms" in names)
    has_r4 = "__rpg" in names or "_ds_menu.dat" in names or "akmenu4.nds" in names

    if has_3ds:
        signatures.extend(["boot.firm", "boot.3dsx", "luma/", "gm9/"])
        if "3ds" in names:
            signatures.append("3ds/")
        if has_twilight:
            signatures.append("TWiLight Menu++ markers")
        confidence = "high" if "luma" in names and "gm9" in names else "medium"
        return StorageValidation("3ds-sd", confidence, tuple(signatures))

    if has_twilight:
        signatures.append("TWiLight Menu++ markers")
        if "roms" in names:
            signatures.append("roms/")
        return StorageValidation("ds-storage", "high", tuple(signatures))

    if has_r4:
        signatures.append("flashcart kernel markers")
        return StorageValidation("ds-flashcart", "medium", tuple(signatures))

    if "roms" in names:
        signatures.append("roms/")
    if "_nds" in names:
        signatures.append("_nds/")
    return StorageValidation("unknown", "low", tuple(signatures))
