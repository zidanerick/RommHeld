from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from .romm_remote import _items, _json_request, _list_games_for_platform_slugs
from .three_ds_targets import RETROARCH_PLATFORM_SLUGS


class RomMLibraryWorker(QThread):
    """Fetch a large compatible RomM library incrementally in API pages."""

    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, instance_url: str, token: str, *, page_size: int = 200):
        super().__init__()
        self.instance_url = instance_url
        self.token = token
        self.page_size = max(1, min(page_size, 500))

    def _load(self, allowed_slugs, missing_message: str) -> None:
        platforms = _items(_json_request(self.instance_url, self.token, "platforms"))
        wanted = [
            item
            for item in platforms
            if isinstance(item, dict)
            and str(item.get("slug", "")).lower() in allowed_slugs
            and isinstance(item.get("id"), int)
        ]
        if not wanted:
            raise RuntimeError(missing_message)

        offset = 0
        while True:
            batch = _list_games_for_platform_slugs(
                self.instance_url,
                self.token,
                allowed_slugs,
                limit=self.page_size,
                offset=offset,
                missing_message=missing_message,
                platform_items=wanted,
            )
            if not batch:
                break
            self.loaded.emit(batch)
            if len(batch) < self.page_size:
                break
            offset += len(batch)

    def run(self) -> None:
        try:
            self._load(
                RETROARCH_PLATFORM_SLUGS,
                "RomM has no platforms currently recognised as compatible with the 3DS targets.",
            )
        except Exception as exc:
            self.failed.emit(str(exc))


class RomM3DSLibraryWorker(RomMLibraryWorker):
    """Compatibility wrapper retained for older callers and tests."""

    def run(self) -> None:
        try:
            self._load({"3ds"}, "RomM has no Nintendo 3DS platform (slug: 3ds).")
        except Exception as exc:
            self.failed.emit(str(exc))
