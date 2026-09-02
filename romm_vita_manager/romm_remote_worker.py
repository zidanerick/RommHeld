from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from .romm_remote import _items, _json_request, _list_games_for_platform_slugs
from .three_ds_targets import RETROARCH_PLATFORM_SLUGS


class RomMLibraryWorker(QThread):
    """Fetch one page of a compatible RomM library in the background."""

    loaded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        instance_url: str,
        token: str,
        *,
        page_size: int = 100,
        offset: int = 0,
        search_term: str = "",
        platform_slug: str | None = None,
    ):
        super().__init__()
        self.instance_url = instance_url
        self.token = token
        self.page_size = max(1, min(page_size, 500))
        self.offset = max(0, offset)
        self.search_term = search_term
        self.platform_slug = platform_slug

    def run(self) -> None:
        try:
            platforms = _items(_json_request(self.instance_url, self.token, "platforms"))
            allowed = RETROARCH_PLATFORM_SLUGS
            wanted = [
                item
                for item in platforms
                if isinstance(item, dict)
                and str(item.get("slug", "")).lower() in allowed
                and isinstance(item.get("id"), int)
            ]
            if self.platform_slug:
                wanted = [
                    item for item in wanted
                    if str(item.get("slug", "")).lower() == self.platform_slug.lower()
                ]
            if not wanted:
                raise RuntimeError("RomM has no platforms currently recognised as compatible with the 3DS targets.")

            batch = _list_games_for_platform_slugs(
                self.instance_url,
                self.token,
                allowed,
                limit=self.page_size,
                offset=self.offset,
                missing_message="RomM has no platforms currently recognised as compatible with the 3DS targets.",
                platform_items=wanted,
                search_term=self.search_term,
                platform_slug=self.platform_slug,
            )
            self.loaded.emit(batch)
        except Exception as exc:
            self.failed.emit(str(exc))


class RomM3DSLibraryWorker(RomMLibraryWorker):
    """Compatibility wrapper retained for older callers and tests."""

    def run(self) -> None:
        try:
            platforms = _items(_json_request(self.instance_url, self.token, "platforms"))
            wanted = [
                item for item in platforms
                if isinstance(item, dict)
                and str(item.get("slug", "")).lower() == "3ds"
                and isinstance(item.get("id"), int)
            ]
            if not wanted:
                raise RuntimeError("RomM has no Nintendo 3DS platform (slug: 3ds).")
            batch = _list_games_for_platform_slugs(
                self.instance_url,
                self.token,
                {"3ds"},
                limit=self.page_size,
                offset=self.offset,
                missing_message="RomM has no Nintendo 3DS platform (slug: 3ds).",
                platform_items=wanted,
                search_term=self.search_term,
                platform_slug="3ds",
            )
            self.loaded.emit(batch)
        except Exception as exc:
            self.failed.emit(str(exc))
