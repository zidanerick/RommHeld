from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from .platform_assets import get_platform_assets


MAX_HARDWARE_IMAGE_BYTES = 16 * 1024 * 1024


class ConsoleIdentity(QWidget):
    """Render optional hardware photos with bundled vectors as the offline fallback."""

    # These are deliberately card-sized rather than source-art-sized. The
    # selector reserves space below the hardware for title, capability summary,
    # and support state, so oversized images must not force those labels out of
    # the card on Linux Qt styles.
    DISPLAY_SIZE = {
        "vita": (176, 78),
        "3ds": (104, 96),
        "ds": (104, 96),
        "psp": (174, 84),
        "mobile": (104, 78),
    }

    def __init__(self, console_key: str, name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.console_key = console_key
        self.name = name
        self.assets = get_platform_assets(console_key)
        self._network = QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None
        self._download = bytearray()
        width, height = self.DISPLAY_SIZE.get(console_key, (150, 82))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.device = QLabel()
        self.device.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.device.setFixedSize(width, height)
        self.device.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.device.setStyleSheet("background:transparent;border:none;")
        root.addWidget(self.device, 0, Qt.AlignmentFlag.AlignCenter)

        self.name_label = QLabel(self.name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(False)
        self.name_label.setStyleSheet(
            "background:transparent;border:none;color:#F5F5F7;font-size:13px;font-weight:700;"
        )
        root.addWidget(self.name_label, 0, Qt.AlignmentFlag.AlignCenter)

        self._load_fallback_artwork()
        self._load_photo()

    def _load_fallback_artwork(self) -> None:
        if not self.assets:
            return
        try:
            artwork_path: Path = self.assets.path("device_large")
        except ValueError:
            return
        if not artwork_path.is_file():
            return
        pixmap = QPixmap(str(artwork_path))
        if pixmap.isNull():
            return
        self.device.setPixmap(self._fit_pixmap(pixmap))

    def _cache_path(self) -> Path:
        cache_root = Path.home() / ".cache" / "rommheld" / "handhelds"
        cache_root.mkdir(parents=True, exist_ok=True)
        return cache_root / f"{self.console_key}.png"

    def _load_photo(self) -> None:
        if not self.assets or not self.assets.photo_url:
            return

        cache_path = self._cache_path()
        if cache_path.is_file():
            pixmap = QPixmap(str(cache_path))
            if not pixmap.isNull():
                self.device.setPixmap(self._fit_photo(pixmap))
                return

        request = QNetworkRequest(QUrl(self.assets.photo_url))
        request.setRawHeader(b"User-Agent", b"RommHeld/1.0 hardware-artwork")
        self._download.clear()
        self._reply = self._network.get(request)
        self._reply.readyRead.connect(self._photo_ready_read)
        self._reply.finished.connect(self._photo_finished)

    def _photo_ready_read(self) -> None:
        reply = self._reply
        if reply is None:
            return
        self._download.extend(bytes(reply.readAll()))
        if len(self._download) > MAX_HARDWARE_IMAGE_BYTES:
            self._download.clear()
            reply.abort()

    def _photo_finished(self) -> None:
        reply = self._reply
        if reply is None:
            return

        if reply.bytesAvailable() and len(self._download) <= MAX_HARDWARE_IMAGE_BYTES:
            self._download.extend(bytes(reply.readAll()))

        data = (
            bytes(self._download)
            if len(self._download) <= MAX_HARDWARE_IMAGE_BYTES
            else b""
        )
        succeeded = (
            reply.error() == QNetworkReply.NetworkError.NoError and bool(data)
        )
        reply.deleteLater()
        self._reply = None
        self._download.clear()

        if not succeeded:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        try:
            pixmap.save(str(self._cache_path()), "PNG")
        except OSError:
            pass
        self.device.setPixmap(self._fit_photo(pixmap))

    def stop_loading(self) -> None:
        reply = self._reply
        if reply is not None and reply.isRunning():
            reply.abort()

    def _fit_pixmap(self, pixmap: QPixmap) -> QPixmap:
        return pixmap.scaled(
            self.device.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _fit_photo(self, pixmap: QPixmap) -> QPixmap:
        target = self.device.size()
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)

        if self.assets and self.assets.photo_remove_white:
            preview = image.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            for y in range(preview.height()):
                for x in range(preview.width()):
                    pixel = preview.pixelColor(x, y)
                    if (
                        pixel.red() >= 245
                        and pixel.green() >= 245
                        and pixel.blue() >= 245
                    ):
                        pixel.setAlpha(0)
                        preview.setPixelColor(x, y, pixel)
            image = preview
        else:
            image = image.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        left = image.width()
        top = image.height()
        right = -1
        bottom = -1
        for y in range(image.height()):
            for x in range(image.width()):
                if image.pixelColor(x, y).alpha() > 8:
                    left = min(left, x)
                    top = min(top, y)
                    right = max(right, x)
                    bottom = max(bottom, y)
        if right >= left and bottom >= top:
            image = image.copy(left, top, right - left + 1, bottom - top + 1)

        return QPixmap.fromImage(image)

    def closeEvent(self, event) -> None:
        self.stop_loading()
        super().closeEvent(event)
