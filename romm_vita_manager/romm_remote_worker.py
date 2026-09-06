from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QThread, Signal

from .romm_library_cache import load_cached_page
from .romm_remote import _as_int, _items, _json_request, _list_games_for_platform_slugs


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

# Existing ThreeDSLibraryWidget stores an integer cursor. For all-platform
# browsing, encode the platform position in the high bits and the ROM offset in
# the low bits so that old callers can keep treating the cursor as an opaque int.
_CURSOR_SHIFT = 32
_CURSOR_MASK = (1 << _CURSOR_SHIFT) - 1


def _encode_cursor(platform_index: int, rom_offset: int) -> int:
    return (max(0, platform_index) << _CURSOR_SHIFT) | (max(0, rom_offset) & _CURSOR_MASK)


def _decode_cursor(value: int) -> tuple[int, int]:
    value = max(0, int(value))
    return value >> _CURSOR_SHIFT, value & _CURSOR_MASK


def _legacy_3ds_scope() -> frozenset[str]:
    """Return the current 3DS scope for callers not yet passing one explicitly."""
    from .three_ds_targets import RETROARCH_PLATFORM_SLUGS

    return frozenset(str(slug).lower() for slug in RETROARCH_PLATFORM_SLUGS)


class RomMLibraryWorker(QThread):
    """Fetch a provider-scoped RomM library incrementally.

    The worker owns remote query/pagination only. Target/runtime/destination
    decisions stay with the caller. Existing 3DS callers can omit an explicit
    scope during migration; future Vita/DS consumers should pass their own
    allowed platform set and cache scope key.
    """

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
        allowed_platform_slugs: Iterable[str] | None = None,
        scope_label: str = "3DS targets",
        scope_key: str = "3ds",
        platform_priority: Iterable[str] | None = None,
    ):
        super().__init__()
        self.instance_url = instance_url
        self.token = token
        self.page_size = max(1, min(page_size, 500))
        self.offset = max(0, offset)
        self.search_term = search_term
        self.platform_slug = platform_slug
        allowed = allowed_platform_slugs if allowed_platform_slugs is not None else _legacy_3ds_scope()
        self.allowed_platform_slugs = frozenset(
            str(slug).strip().lower() for slug in allowed if str(slug).strip()
        )
        self.scope_label = str(scope_label or "configured target").strip()
        self.scope_key = str(scope_key or "default").strip().casefold()
        priority = tuple(platform_priority) if platform_priority is not None else _PLATFORM_PRIORITY
        self.platform_priority = tuple(str(slug).strip().lower() for slug in priority)
        self.platforms_consumed = 0
        self.platforms_total = 0

    def _missing_message(self) -> str:
        return f"RomM has no platforms currently recognised as compatible with {self.scope_label}."

    def _wanted_platforms(self, platforms):
        wanted = [
            item
            for item in platforms
            if isinstance(item, dict)
            and str(item.get("slug", "")).lower() in self.allowed_platform_slugs
            and _as_int(item.get("id")) is not None
        ]
        if self.platform_slug:
            wanted = [
                item
                for item in wanted
                if str(item.get("slug", "")).lower() == self.platform_slug.lower()
            ]
        priority = {slug: index for index, slug in enumerate(self.platform_priority)}
        return sorted(
            wanted,
            key=lambda item: (
                0 if _as_int(item.get("rom_count") or item.get("roms_count")) else 1,
                priority.get(str(item.get("slug", "")).lower(), len(priority)),
                str(item.get("name") or item.get("slug") or "").casefold(),
            ),
        )

    def _cached_platform_options(self) -> list[dict[str, str]]:
        try:
            cached = load_cached_page(
                self.instance_url,
                self.search_term,
                self.platform_slug,
                scope_key=self.scope_key,
            )
        except Exception:
            return []

        by_slug: dict[str, str] = {}
        for game in cached:
            slug = str(game.platform_slug or game.platform).strip().lower()
            if not slug or slug not in self.allowed_platform_slugs:
                continue
            label = str(game.platform or slug).strip() or slug
            by_slug.setdefault(slug, label)
        return [
            {"slug": slug, "name": by_slug[slug]}
            for slug in sorted(by_slug, key=lambda value: by_slug[value].casefold())
        ]

    def _fetch_platform(
        self,
        platform: dict,
        *,
        limit: int | None = None,
        offset: int = 0,
    ):
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
            offset=max(0, offset),
            missing_message=self._missing_message(),
            platform_items=[platform],
            search_term=self.search_term,
            platform_slug=slug,
        )

    def _run_selected_platform(self, wanted: list[dict]) -> None:
        platform = wanted[0]
        self.platforms_total = 1
        self.platforms_consumed = 1
        self.progress.emit(
            f"RomM: loading {platform.get('name') or self.platform_slug}…"
        )
        results = self._fetch_platform(platform, offset=self.offset)
        if not self.isInterruptionRequested():
            self.loaded.emit(results)

    def _run_all_platforms(self, wanted: list[dict]) -> None:
        start_index, start_rom_offset = _decode_cursor(self.offset)
        start_index = min(start_index, len(wanted))
        total_cursor = _encode_cursor(len(wanted), 0)
        self.platforms_total = total_cursor

        if start_index >= len(wanted):
            self.platforms_consumed = max(0, total_cursor - self.offset)
            self.loaded.emit([])
            return

        collected: list = []
        next_cursor = self.offset

        for index in range(start_index, len(wanted)):
            if self.isInterruptionRequested():
                return
            platform = wanted[index]
            slug = str(platform.get("slug") or "").lower()
            platform_offset = start_rom_offset if index == start_index else 0
            self.progress.emit(f"RomM: checking {platform.get('name') or slug}…")

            remaining = self.page_size - len(collected)
            if remaining <= 0:
                break
            request_limit = min(500, remaining + 1)

            try:
                results = self._fetch_platform(
                    platform,
                    limit=request_limit,
                    offset=platform_offset,
                )
            except Exception as exc:
                if self.isInterruptionRequested():
                    return
                self.progress.emit(f"RomM: {platform.get('name') or slug} failed: {exc}")
                next_cursor = _encode_cursor(index + 1, 0)
                continue

            if self.isInterruptionRequested():
                return
            if not results:
                next_cursor = _encode_cursor(index + 1, 0)
                continue

            take = results[:remaining]
            collected.extend(take)
            self.progress.emit(
                f"RomM: received {len(take):,} result{'s' if len(take) != 1 else ''} from "
                f"{platform.get('name') or slug}."
            )

            more_on_platform = len(results) > remaining or (
                remaining >= 500 and len(results) == remaining
            )
            if more_on_platform:
                next_cursor = _encode_cursor(index, platform_offset + len(take))
                break

            next_cursor = _encode_cursor(index + 1, 0)
            if len(collected) >= self.page_size:
                break

        if next_cursor < self.offset:
            next_cursor = self.offset
        self.platforms_consumed = next_cursor - self.offset
        if not collected and next_cursor >= total_cursor:
            # Existing UI only advances its cursor for non-empty batches. Make an
            # empty terminal page self-identifying so it can still mark end-of-library.
            self.platforms_total = self.offset
        self.loaded.emit(collected)

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
                and str(item.get("slug", "")).lower() in self.allowed_platform_slugs
            ]
            self.platforms_loaded.emit(compatible)
            wanted = self._wanted_platforms(platforms)
            self.progress.emit(f"RomM: found {len(wanted):,} compatible platform(s).")
            if not wanted:
                raise RuntimeError(self._missing_message())

            if self.platform_slug:
                self._run_selected_platform(wanted)
            else:
                self._run_all_platforms(wanted)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))


class RomM3DSLibraryWorker(RomMLibraryWorker):
    """Compatibility wrapper retained for older 3DS-only callers and tests."""

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
