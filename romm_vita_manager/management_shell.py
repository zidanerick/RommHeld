from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .platform_assets import get_platform_assets


@dataclass(frozen=True)
class WorkspaceProfile:
    key: str
    name: str
    accent: str
    secondary: str
    description: str


WORKSPACE_PROFILES = {
    "vita": WorkspaceProfile("vita", "PlayStation Vita", "#41a6f6", "#17324d", "USB / VitaShell, RetroFlow and Adrenaline"),
    "3ds": WorkspaceProfile("3ds", "Nintendo 3DS", "#d12228", "#4a1212", "FTP / SD card and native 3DS runtimes"),
    "ds": WorkspaceProfile("ds", "Nintendo DS", "#54b8ff", "#122a45", "TWiLight Menu++, nds-bootstrap and flashcards"),
}


class ManagementShell(QWidget):
    """Shared game-like management shell for device-specific workspaces."""

    navigation_requested = Signal(str)
    change_handheld_requested = Signal()

    def __init__(self, profile: WorkspaceProfile, parent: QWidget | None = None):
        super().__init__(parent)
        self.profile = profile
        self.setObjectName("managementShell")
        self.setStyleSheet(self._stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        header = QFrame()
        header.setObjectName("workspaceHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        logo = QLabel()
        logo.setFixedSize(QSize(150, 46))
        assets = get_platform_assets(profile.key)
        if assets:
            logo_path = assets.path("logo_dark")
            if logo_path.is_file():
                logo.setPixmap(QPixmap(str(logo_path)).scaled(145, 42, aspectMode=1, mode=1))
        header_layout.addWidget(logo)
        title_layout = QVBoxLayout()
        title = QLabel(profile.name.upper())
        title.setObjectName("workspaceTitle")
        subtitle = QLabel(profile.description)
        subtitle.setObjectName("workspaceSubtitle")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header_layout.addLayout(title_layout, 1)
        change = QPushButton("CHANGE HANDHELD")
        change.setObjectName("changeButton")
        change.clicked.connect(self.change_handheld_requested.emit)
        header_layout.addWidget(change)
        root.addWidget(header)

        nav = QFrame()
        nav.setObjectName("workspaceNav")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(8, 6, 8, 6)
        for label in ("LIBRARY", "DEVICE", "SETUP", "QUEUE", "TOOLS", "SETTINGS"):
            key = label.lower()
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.clicked.connect(lambda _checked=False, value=key: self.navigation_requested.emit(value))
            nav_layout.addWidget(button)
        nav_layout.addStretch()
        root.addWidget(nav)

        self.content = QFrame()
        self.content.setObjectName("workspaceContent")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.content, 1)

        footer = QFrame()
        footer.setObjectName("workspaceFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(10, 5, 10, 5)
        footer_layout.addWidget(QLabel("DEVICE STATUS"))
        footer_layout.addStretch()
        root.addWidget(footer)

    def set_content(self, widget: QWidget) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(None)
        self.content_layout.addWidget(widget)

    def _stylesheet(self) -> str:
        p = self.profile
        return f"""
        QWidget#managementShell {{ background:#0a0d12; color:#eef1f5; }}
        QFrame#workspaceHeader {{ background:{p.secondary}; border:2px solid {p.accent}; border-radius:16px; }}
        QLabel#workspaceTitle {{ color:{p.accent}; font-size:20px; font-weight:900; letter-spacing:2px; }}
        QLabel#workspaceSubtitle {{ color:#abb4c0; font-size:11px; }}
        QPushButton#changeButton {{ background:transparent; border:1px solid {p.accent}; color:#eef1f5; padding:7px 11px; border-radius:8px; font-weight:800; }}
        QPushButton#changeButton:hover {{ background:{p.accent}; color:#081019; }}
        QFrame#workspaceNav {{ background:#12161c; border:1px solid #2a3039; border-radius:12px; }}
        QPushButton#navButton {{ background:transparent; border:1px solid transparent; color:#b9c0ca; padding:7px 12px; font-weight:800; border-radius:8px; }}
        QPushButton#navButton:hover {{ color:#ffffff; border-color:{p.accent}; }}
        QFrame#workspaceContent {{ background:#0f1319; border:1px solid #292f38; border-radius:14px; }}
        QFrame#workspaceFooter {{ background:#12161c; border-top:2px solid {p.accent}; }}
        """
