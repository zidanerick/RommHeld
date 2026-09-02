from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from .platform_assets import get_platform_assets


class ConsoleIdentity(QWidget):
    """Render a bundled handheld icon and clean platform name."""

    def __init__(self, console_key: str, name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.console_key = console_key
        self.name = name
        self.assets = get_platform_assets(console_key)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.device = QLabel()
        self.device.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.device.setFixedSize(120, 120)
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

        self._load_icon()

    def _load_icon(self) -> None:
        if not self.assets:
            return
        icon_name = getattr(self.assets, "icons8_icon", None)
        if not icon_name:
            return
        icon_path: Path = self.assets.path("icons8_icon")
        if not icon_path.is_file():
            return

        pixmap = QPixmap(str(icon_path))
        if pixmap.isNull():
            return
        self.device.setPixmap(
            pixmap.scaled(
                100,
                100,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
