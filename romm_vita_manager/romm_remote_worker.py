from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from .romm_library_cache import load_cached_page
from .romm_remote import _as_int, _items, _json_request, _list_games_for_platform_slugs
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
    """Fetch RomM library data incrementally so the UI never waits for a batch of platforms."""

    loaded = Signal(object)
    platforms_loaded = Signal(object)
    progress = Signal(str)
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
        self.platforms_consumed = 0
        self.platforms_total = 0

    def _wanted_platforms(self, platforms):
        wanted = [
            item
            for item in platforms
            if isinstance(item, dict)
            and str(item.get("slug", "")).lower() in RETROARCH_PLATFORM_SLUGS
            and _as_int(item.get("id")) is not None
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
                0 if _as_int(item.get("rom_count") or item.get("roms_count")) else 1,
                priority.get(str(item.get("slug", "")).lower(), len(priority)),
                str(item.get("name") or item.get("slug") or "").casefold(),
            ),
        )

    def _cached_platform_options(self) -> list[dict[str, str]]:
        """Return platform labels recoverable from the cached page shown by the UI.

        The 3DS library displays cached games before a fresh RomM request completes.
        Emitting these options immediately keeps the platform filter consistent with
        the rows already visible instead of leaving it at only "All compatible
        platforms" until the remote /platforms request returns.
        """
        try:
            cached = load_cached_page(
                self.instance_url,
                self.search_term,
                self.platform_slug,
            )
        except Exception:
            return []

        by_slug: dict[str, str] = {}
        for game in cached:
            slug = str(game.platform_slug or game.platform).strip().lower()
            if not slug or slug not in RETROARCH_PLATFORM_SLUGS:
                continue
            label = str(game.platform or slug).strip() or slug
            by_slug.setdefault(slug, label)
        return [
            {"slug": slug, "name": by_slug[slug]}
            for slug in sorted(by_slug, key=lambda value: by_slug[value].casefold())
        ]

    def _fetch_platform(self, platform: dict, *, limit: int | None = None):
        if self.isInterruptionRequested():
            return []
        slug = str(platform.get("slug") or "").lower()
        if not slug:
            return []
        return _list_games_for_platform_slugs(
            self.instance_url,
            self.token,
            {slug},
            limit=limit or self.page_size,
            offset=self.offset if self.platform_slug else 0,
            missing_message="RomM has no platforms currently recognised as compatible with the 3DS targets.",
            platform_items=[platform],
            search_term=self.search_term,
            platform_slug=slug,
        )

    def _emit_platform_results(self, platform: dict, consumed: int, results: list) -> int:
        if self.isInterruptionRequested():
            return 0
        self.platforms_consumed = consumed
        if not results:
            return 0
        self.progress.emit(
            f"RomM: received {len(results):,} result{'s' if len(results) != 1 else ''} from "
            f"{platform.get('name') or platform.get('slug')}."
        )
        self.loaded.emit(results[: self.page_size])
        return len(results)

    def run(self) -> None:
        try:
            if self.isInterruptionRequested():
                return
            cached_platforms = self._cached_platform_options()
            if cached_platforms:
                self.platforms_loaded.emit(cached_platforms)
            self.progress.emit("Connecting to RomM…")
            platforms = _items(_json_request(self.instance_url, self.token, "platforms"))
            if self.isInterruptionRequested():
                return
            compatible = [
                item
                for item in platforms
                if isinstance(item, dict)
                and str(item.get("slug", "")).lower() in RETROARCH_PLATFORM_SLUGS
            ]
            self.platforms_loaded.emit(compatible)
            wanted = self._wanted_platforms(platforms)
            self.platforms_total = len(wanted)
            self.progress.emit(f"RomM: found {len(wanted):,} compatible platform(s).")
            if not wanted:
                raise RuntimeError("RomM has no platforms currently recognised as compatible with the 3DS targets.")

            if self.platform_slug:
                if self.isInterruptionRequested():
                    return
                platform = wanted[0]
                self.progress.emit(f"RomM: loading {platform.get('name') or self.platform_slug}…")
                results = self._fetch_platform(platform)
                if self.isInterruptionRequested():
                    return
                self.platforms_consumed = 1
                self.loaded.emit(results)
                return

            start = min(self.offset, len(wanted))
            collected = 0
            for index in range(start, len(wanted)):
                if self.isInterruptionRequested():
                    return
                platform = wanted[index]
                slug = str(platform.get("slug") or "").lower()
                self.progress.emit(f"RomM: checking {platform.get('name') or slug}…")
                try:
                    if collected == 0:
                        # Keep the first validation request tiny. This confirms
                        # authentication and ROM access before requesting a page.
                        probe = self._fetch_platform(platform, limit=1)
                        if self.isInterruptionRequested():
                            return
                        if probe:
                            self.progress.emit(
                                f"RomM: API probe succeeded with {platform.get('name') or slug}; loading its library page…"
                            )
                        else:
                            self.progress.emit(f"RomM: {platform.get('name') or slug} has no matching ROMs on this query.")
                    results = self._fetch_platform(platform)
                    if self.isInterruptionRequested():
                        return
                except Exception as exc:
                    if self.isInterruptionRequested():
                        return
                    self.progress.emit(f"RomM: {platform.get('name') or slug} failed: {exc}")
                    continue

                self.platforms_consumed = index + 1
                if not results:
                    continue

                collected += self._emit_platform_results(platform, index + 1, results)
                if collected >= self.page_size:
                    break

        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))


class RomM3DSLibraryWorker(RomMLibraryWorker):
    """Compatibility wrapper retained for older callers and tests."""

    def run(self) -> None:
        try:
            if self.isInterruptionRequested():
                return
            cached_platforms = self._cached_platform_options()
            if cached_platforms:
                self.platforms_loaded.emit(cached_platforms)
            platforms = _items(_json_request(self.instance_url, self.token, "platforms"))
            if self.isInterruptionRequested():
                return
            wanted = [
                item
                for item in platforms
                if isinstance(item, dict)
                and str(item.get("slug", "")).lower() == "3ds"
                and _as_int(item.get("id")) is not None
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
            if not self.isInterruptionRequested():
                self.loaded.emit(batch)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))
