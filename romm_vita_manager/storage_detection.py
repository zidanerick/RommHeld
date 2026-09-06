from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .platform_services import writable_volumes, volume_info
from .storage_validation import StorageValidation, validate_3ds_sd


@dataclass(frozen=True)
class StorageCandidate:
    root: Path
    validation: StorageValidation
    filesystem: str = ""
    label: str = ""


def detect_3ds_sd_candidates() -> list[StorageCandidate]:
    candidates: list[StorageCandidate] = []
    for root in writable_volumes():
        try:
            validation = validate_3ds_sd(root)
        except (OSError, ValueError):
            continue
        # Automatic suggestions must meet the same confidence threshold used
        # for actual 3DS SD writes. Generic ROM libraries often contain
        # directories named ``roms`` or ``3ds`` and must not be presented as
        # possible console media on that evidence alone.
        if validation.confidence not in {"medium", "high"}:
            continue
        info = volume_info(root)
        candidates.append(
            StorageCandidate(
                root=root,
                validation=validation,
                filesystem=str(info.get("filesystem", "")),
                label=str(info.get("display_name") or info.get("name") or ""),
            )
        )
    candidates.sort(
        key=lambda item: (
            item.validation.confidence != "high",
            -item.validation.matched_count,
            str(item.root).lower(),
        )
    )
    return candidates
