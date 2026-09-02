from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from .romm_api import RomMApiError, normalize_romm_url, test_connection


class RomMStartupVerifier(QThread):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, url: str, token: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.token = token

    def run(self) -> None:
        try:
            test_connection(normalize_romm_url(self.url), self.token)
        except (RomMApiError, ValueError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Unexpected connection error: {exc}")
        else:
            self.succeeded.emit("RomM connected • API access verified")
