from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from .platform_assets import PlatformAssets, get_platform_assets


class ConsoleIdentity(QWidget):
    """Render handheld artwork and platform identity without forcing one logo shape."""

    def __init__(self, console_key: str, name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.console_key = console_key
        self.name = name
        self.assets: PlatformAssets | None = get_platform_assets(console_key)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        self.device = QLabel()
        self.device.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.device.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.device.setMinimumHeight(108)
        root.addWidget(self.device)

        self.identity = QLabel()
        self.identity.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.identity.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.identity.setMinimumHeight(38)
        root.addWidget(self.identity)

        self._load_images()

    def _scaled(self, path: Path, max_width: int, max_height: int) -> QPixmap:
        pixmap = QPixmap(str(path))
        return pixmap.scaled(
            max_width,
            max_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _load_images(self) -> None:
        if not self.assets:
            self.identity.setText(self.name.upper())
            return

        device_path = self.assets.path("device_large")
        if device_path.is_file():
            self.device.setPixmap(self._scaled(device_path, 150, 112))

        identity_layout = QHBoxLayout(self.identity)
        identity_layout.setContentsMargins(0, 0, 0, 0)
        identity_layout.setSpacing(8)
        identity_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        role = getattr(self.assets, "logo_role", "wordmark")
        logo_kind = "logo_dark"
        if role == "icon" and getattr(self.assets, "logo_simpleicons_dark", None):
            logo_kind = "logo_simpleicons_dark"

        try:
            logo_path = self.assets.path(logo_kind)
        except (AttributeError, ValueError):
            logo_path = self.assets.path("logo_dark")

        if logo_path.is_file():
            max_width = 180 if role == "wordmark" else 42
            max_height = 34 if role == "wordmark" else 42
            logo = QLabel()
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo.setPixmap(self._scaled(logo_path, max_width, max_height))
            logo.setStyleSheet("background:transparent;border:none;")
            identity_layout.addWidget(logo)

        # 3DS uses a compact brand icon, while Vita/DS wordmarks already carry the name.
        if role == "icon":
            name_label = QLabel(self.name.upper())
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setStyleSheet(
                "background:transparent;border:none;color:#f2f4f8;font-size:12px;font-weight:700;"
            )
            identity_layout.addWidget(name_label)

        if role not in {"icon", "wordmark"}:
            fallback = QLabel(self.name.upper())
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fallback.setStyleSheet(
                "background:transparent;border:none;color:#f2f4f8;font-size:12px;font-weight:700;"
            )
            identity_layout.addWidget(fallback)
