from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import QThread, Signal

from .romm_remote import _items, _json_request, _list_games_for_platform_slugs
from .three_ds_targets import RETROARCH_PLATFORM_SLUGS


_PLATFORM_PRIORITY = (
    "3ds",
    "gba",
    "gb",
    "gbc",
    "snes",
    "nes",
    "fds",
    "gamegear",
    "sms",
    "genesis",
)


class RomMLibraryWorker(QThread):
    """Fetch a bounded slice of the compatible RomM library without one giant query."""

    loaded = Signal(object)
    platforms_loaded = Signal(object)
    failed = Signal(str)

    PLATFORM_BATCH_SIZE = 4

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
        self.platforms_consumed = 0
        self.platforms_total = 0

    def _wanted_platforms(self, platforms):
        wanted = [
            item
            for item in platforms
            if isinstance(item, dict)
            and str(item.get("slug", "")).lower() in RETROARCH_PLATFORM_SLUGS
            and isinstance(item.get("id"), int)
        ]
        if self.platform_slug:
            wanted = [
                item for item in wanted
                if str(item.get("slug", "")).lower() == self.platform_slug.lower()
            ]
        priority = {slug: index for index, slug in enumerate(_PLATFORM_PRIORITY)}
        return sorted(
            wanted,
            key=lambda item: (
                0 if int(item.get("rom_count") or item.get("roms_count") or 0) > 0 else 1,
                priority.get(str(item.get("slug", "")).lower(), len(priority)),
                str(item.get("name") or item.get("slug") or "").casefold(),
            ),
        )

    def _fetch_platform(self, platform: dict, limit: int):
        slug = str(platform.get("slug") or "").lower()
        if not slug:
            return []
        return _list_games_for_platform_slugs(
            self.instance_url,
            self.token,
            {slug},
            limit=limit,
            offset=0,
            missing_message="RomM has no platforms currently recognised as compatible with the 3DS targets.",
            platform_items=[platform],
            search_term=self.search_term,
            platform_slug=slug,
        )

    def _fetch_batch(self, platforms: list[dict]) -> list:
        if not platforms:
            return []
        per_platform = max(1, self.page_size // len(platforms))
        results: dict[str, list] = {}
        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=len(platforms)) as executor:
            pending = {
                executor.submit(self._fetch_platform, platform, per_platform): str(platform.get("slug") or "").lower()
                for platform in platforms
            }
            for future in as_completed(pending):
                slug = pending[future]
                try:
                    results[slug] = list(future.result())
                except Exception as exc:
                    errors.append(f"{slug}: {exc}")
        ordered: list = []
        for platform in platforms:
            ordered.extend(results.get(str(platform.get("slug") or "").lower(), []))
        if not ordered and errors and len(errors) == len(platforms):
            raise RuntimeError("; ".join(errors))
        return ordered

    def _fetch_all_platforms(self, wanted: list[dict]) -> list:
        """Fill one UI page by walking small platform groups until full or exhausted."""
        start = min(self.offset, len(wanted))
        consumed = 0
        collected: list = []
        while start < len(wanted):
            group = wanted[start:start + self.PLATFORM_BATCH_SIZE]
            results = self._fetch_batch(group)
            consumed += len(group)
            start += len(group)
            collected.extend(results)
            if len(collected) >= self.page_size:
                break
        self.platforms_consumed = consumed
        return collected[:self.page_size]

    def _fetch_browse(self, wanted: list[dict]) -> list:
        if self.platform_slug:
            return _list_games_for_platform_slugs(
                self.instance_url,
                self.token,
                {self.platform_slug.lower()},
                limit=self.page_size,
                offset=self.offset,
                missing_message="RomM has no platforms currently recognised as compatible with the 3DS targets.",
                platform_items=[wanted[0]],
                search_term=self.search_term,
                platform_slug=self.platform_slug,
            )
        return self._fetch_all_platforms(wanted)

    def run(self) -> None:
        try:
            platforms = _items(_json_request(self.instance_url, self.token, "platforms"))
            compatible = [
                item for item in platforms
                if isinstance(item, dict)
                and str(item.get("slug", "")).lower() in RETROARCH_PLATFORM_SLUGS
            ]
            self.platforms_loaded.emit(compatible)
            wanted = self._wanted_platforms(platforms)
            self.platforms_total = len(wanted)
            if not wanted:
                raise RuntimeError("RomM has no platforms currently recognised as compatible with the 3DS targets.")

            batch = self._fetch_browse(wanted)
            self.loaded.emit(batch)
        except Exception as exc:
            self.failed.emit(str(exc))


class RomM3DSLibraryWorker(RomMLibraryWorker):
    """Compatibility wrapper retained for older callers and tests."""

    def run(self) -> None:
        try:
            platforms = _items(_json_request(self.instance_url, self.token, "platforms"))
            wanted = [
                item
                for item in platforms
                if isinstance(item, dict)
                and str(item.get("slug", "")).lower() == "3ds"
                and isinstance(item.get("id"), int)
            ]
            self.platforms_total = len(wanted)
            self.platforms_consumed = len(wanted)
            self.platforms_loaded.emit(wanted)
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
