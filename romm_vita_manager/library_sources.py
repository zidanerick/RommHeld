from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


ROMM_LIBRARY_WORKSPACES = frozenset({"3ds"})


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


def workspace_supports_library_source(workspace_key: str, mode: str) -> bool:
    """Return whether a workspace currently has a real browser for this source.

    Local-library presentation is implemented for Vita, 3DS and DS. The RomM
    browser/deployment path is currently implemented for 3DS only. Keeping this
    capability explicit prevents onboarding or Settings from saving a source
    that would produce an intentionally empty Library page.
    """
    normalized_workspace = str(workspace_key or "").strip().lower()
    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode == "local":
        return normalized_workspace in {"vita", "3ds", "ds"}
    if normalized_mode == "romm_api":
        return normalized_workspace in ROMM_LIBRARY_WORKSPACES
    return False


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
