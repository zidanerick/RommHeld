from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from .platform_assets import get_platform_assets


class ConsoleIdentity(QWidget):
    """Render bundled, recognisable handheld artwork with no runtime network dependency."""

    DISPLAY_SIZE = {
        "vita": (186, 104),
        "3ds": (168, 132),
        "ds": (168, 132),
        "psp": (186, 120),
    }

    def __init__(self, console_key: str, name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.console_key = console_key
        self.name = name
        self.assets = get_platform_assets(console_key)
        width, height = self.DISPLAY_SIZE.get(console_key, (168, 132))

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

        self._load_artwork()

    def _load_artwork(self) -> None:
        if not self.assets:
            return
        artwork_path: Path = self.assets.path("device_large")
        if not artwork_path.is_file():
            return

        pixmap = QPixmap(str(artwork_path))
        if pixmap.isNull():
            return
        target = self.device.size()
        self.device.setPixmap(
            pixmap.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
