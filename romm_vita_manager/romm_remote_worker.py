from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from .romm_remote import RomMRemoteGame, list_3ds_games


class RomM3DSLibraryWorker(QThread):
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, instance_url: str, token: str):
        super().__init__()
        self.instance_url = instance_url
        self.token = token

    def run(self) -> None:
        try:
            self.loaded.emit(list_3ds_games(self.instance_url, self.token))
        except Exception as exc:
            self.failed.emit(str(exc))
