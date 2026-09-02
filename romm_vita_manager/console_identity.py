from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget


# Icons8 Color-style icons selected from the user's requested handheld-game-console set.
# The Color family is intended for desktop/app UI and is available in PNG/SVG.
ICONS8_URLS = {
    "vita": "https://img.icons8.com/color/96/playstation.png",
    "3ds": "https://img.icons8.com/color/96/3ds-console.png",
    "ds": "https://img.icons8.com/color/96/nintendo-ds.png",
    "psp": "https://img.icons8.com/color/96/playstation-portable.png",
    "mobile": "https://img.icons8.com/color/96/mobile.png",
}


class ConsoleIdentity(QWidget):
    """Clean, fixed-height platform identity using cached Icons8 artwork."""

    def __init__(self, console_key: str, name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.console_key = console_key
        self.name = name
        self._network = QNetworkAccessManager(self)
        self._reply = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(7)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.device = QLabel()
        self.device.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.device.setFixedSize(112, 112)
        self.device.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.device.setStyleSheet("background:transparent;border:none;")
        root.addWidget(self.device, 0, Qt.AlignmentFlag.AlignCenter)

        self.name_label = QLabel(self.name.upper())
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(False)
        self.name_label.setStyleSheet(
            "background:transparent;border:none;color:#f2f4f8;font-size:13px;font-weight:700;"
        )
        root.addWidget(self.name_label)

        self._load_icon()

    def _cache_path(self) -> Path:
        base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation))
        cache = base / "icons8"
        cache.mkdir(parents=True, exist_ok=True)
        return cache / f"{self.console_key}.png"

    def _set_pixmap(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        self.device.setPixmap(
            pixmap.scaled(
                96,
                96,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _load_icon(self) -> None:
        url = ICONS8_URLS.get(self.console_key)
        if not url:
            return

        cache_path = self._cache_path()
        if cache_path.is_file():
            pixmap = QPixmap(str(cache_path))
            if not pixmap.isNull():
                self._set_pixmap(pixmap)
                return

        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", b"RommHeld/1.0")
        self._reply = self._network.get(request)
        self._reply.finished.connect(self._icon_download_finished)

    def _icon_download_finished(self) -> None:
        reply = self._reply
        self._reply = None
        if reply is None:
            return
        try:
            if reply.error() != reply.NetworkError.NoError:
                return
            data = bytes(reply.readAll())
            pixmap = QPixmap()
            if not pixmap.loadFromData(data):
                return
            cache_path = self._cache_path()
            pixmap.save(str(cache_path), "PNG")
            self._set_pixmap(pixmap)
        finally:
            reply.deleteLater()
