from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class LibrarySource:
    mode: str
    local_root: str = ""
    romm_url: str = ""
    api_token: str = ""

    @property
    def display_name(self) -> str:
        if self.mode == "romm_api":
            return "RomM Server"
        return "Local ROM directory"


def get_library_source(config: Mapping[str, object]) -> LibrarySource:
    raw = config.get("library_source", {})
    if not isinstance(raw, Mapping):
        raw = {}
    mode = str(raw.get("mode", "local")).strip().lower()
    if mode not in {"local", "romm_api"}:
        mode = "local"
    return LibrarySource(
        mode=mode,
        local_root=str(raw.get("local_root", config.get("romm_root", ""))),
        romm_url=str(raw.get("romm_url", "")),
        api_token=str(raw.get("api_token", "")),
    )


def save_library_source(config: dict, source: LibrarySource) -> dict:
    updated = dict(config)
    updated["library_source"] = {
        "mode": source.mode,
        "local_root": source.local_root,
        "romm_url": source.romm_url,
        "api_token": source.api_token,
    }
    if source.mode == "local" and source.local_root:
        updated["romm_root"] = source.local_root
    return updated
