from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from .platform_assets import get_platform_assets


class _PhotoLoader(QThread):
    loaded = Signal(bytes)

    def __init__(self, url: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.url = url

    def run(self) -> None:
        try:
            request = Request(
                self.url,
                headers={"User-Agent": "RommHeld/1.0 hardware-artwork"},
            )
            with urlopen(request, timeout=10) as response:
                data = response.read(16 * 1024 * 1024)
            if data:
                self.loaded.emit(data)
        except Exception:
            return


class ConsoleIdentity(QWidget):
    """Render real hardware photos when available, with bundled vectors as an offline fallback."""

    DISPLAY_SIZE = {
        "vita": (198, 96),
        "3ds": (158, 154),
        "ds": (158, 154),
        "psp": (192, 118),
    }

    def __init__(self, console_key: str, name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.console_key = console_key
        self.name = name
        self.assets = get_platform_assets(console_key)
        self._photo_loader: _PhotoLoader | None = None
        width, height = self.DISPLAY_SIZE.get(console_key, (170, 132))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(7)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.device = QLabel()
        self.device.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.device.setFixedSize(width, height)
        self.device.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.device.setStyleSheet("background:transparent;border:none;")
        root.addWidget(self.device, 0, Qt.AlignmentFlag.AlignCenter)

        self.name_label = QLabel(self.name.upper())
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(False)
        self.name_label.setStyleSheet(
            "background:transparent;border:none;color:#f2f4f8;font-size:13px;font-weight:700;"
        )
        root.addWidget(self.name_label, 0, Qt.AlignmentFlag.AlignCenter)

        self._load_fallback_artwork()
        self._load_photo()

    def _load_fallback_artwork(self) -> None:
        if not self.assets:
            return
        artwork_path: Path = self.assets.path("device_large")
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

        self._photo_loader = _PhotoLoader(self.assets.photo_url, self)
        self._photo_loader.loaded.connect(self._photo_loaded)
        self._photo_loader.finished.connect(self._photo_thread_finished)
        self._photo_loader.start()

    def _photo_loaded(self, data: bytes) -> None:
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        try:
            pixmap.save(str(self._cache_path()), "PNG")
        except Exception:
            pass
        self.device.setPixmap(self._fit_photo(pixmap))

    def _photo_thread_finished(self) -> None:
        if self._photo_loader is not None:
            self._photo_loader.deleteLater()
            self._photo_loader = None

    def _fit_pixmap(self, pixmap: QPixmap) -> QPixmap:
        target = self.device.size()
        return pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _fit_photo(self, pixmap: QPixmap) -> QPixmap:
        target = self.device.size()
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)

        # Vita's source image is a white-background photograph. Remove near-white
        # pixels after scaling so the real hardware sits cleanly on the dark UI.
        if self.assets and self.assets.photo_remove_white:
            preview = image.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            for y in range(preview.height()):
                for x in range(preview.width()):
                    pixel = preview.pixelColor(x, y)
                    if pixel.red() >= 245 and pixel.green() >= 245 and pixel.blue() >= 245:
                        pixel.setAlpha(0)
                        preview.setPixelColor(x, y, pixel)
            image = preview
        else:
            image = image.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        # Crop transparent margins introduced by the source photograph/canvas.
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
