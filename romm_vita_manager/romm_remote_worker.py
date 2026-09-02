from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from .romm_remote import RomMRemoteGame, _list_games_for_platform_slugs
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

    def run(self) -> None:
        try:
            offset = 0
            while True:
                batch = _list_games_for_platform_slugs(
                    self.instance_url,
                    self.token,
                    RETROARCH_PLATFORM_SLUGS,
                    limit=self.page_size,
                    offset=offset,
                    missing_message="RomM has no platforms currently recognised as compatible with the 3DS targets.",
                )
                if not batch:
                    break
                self.loaded.emit(batch)
                if len(batch) < self.page_size:
                    break
                offset += len(batch)
        except Exception as exc:
            self.failed.emit(str(exc))


class RomM3DSLibraryWorker(RomMLibraryWorker):
    """Compatibility wrapper retained for older callers and tests."""

    def run(self) -> None:
        try:
            offset = 0
            while True:
                batch = _list_games_for_platform_slugs(
                    self.instance_url,
                    self.token,
                    {"3ds"},
                    limit=self.page_size,
                    offset=offset,
                    missing_message="RomM has no Nintendo 3DS platform (slug: 3ds).",
                )
                if not batch:
                    break
                self.loaded.emit(batch)
                if len(batch) < self.page_size:
                    break
                offset += len(batch)
        except Exception as exc:
            self.failed.emit(str(exc))
