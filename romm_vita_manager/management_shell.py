from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QTabWidget, QVBoxLayout, QWidget

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
    """Single-window management shell with console-aware sections and device status."""

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
        self.logo = QLabel()
        self.logo.setFixedSize(QSize(150, 46))
        self._load_logo()
        header_layout.addWidget(self.logo)
        title_layout = QVBoxLayout()
        self.title = QLabel(profile.name.upper())
        self.title.setObjectName("workspaceTitle")
        subtitle = QLabel(profile.description)
        subtitle.setObjectName("workspaceSubtitle")
        title_layout.addWidget(self.title)
        title_layout.addWidget(subtitle)
        header_layout.addLayout(title_layout, 1)
        change = QPushButton("CHANGE HANDHELD")
        change.setObjectName("changeButton")
        change.clicked.connect(self.change_handheld_requested.emit)
        header_layout.addWidget(change)
        root.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("workspaceTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.currentChanged.connect(self._tab_changed)
        root.addWidget(self.tabs, 1)

        footer = QFrame()
        footer.setObjectName("workspaceFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(10, 4, 10, 4)
        self.footer_section = QLabel(f"{profile.name} • LIBRARY")
        self.footer_section.setObjectName("footerSection")
        footer_layout.addWidget(self.footer_section)
        footer_layout.addStretch()
        self.footer_devices = {}
        for key, label in (("vita", "Vita"), ("3ds", "3DS"), ("ds", "DS")):
            widget = self._make_device_status(label, key)
            self.footer_devices[key] = widget
            footer_layout.addWidget(widget)
        root.addWidget(footer)

    def _make_device_status(self, label: str, key: str) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(6, 0, 6, 0)
        row.setSpacing(4)
        icon = QLabel()
        icon.setFixedSize(18, 18)
        assets = get_platform_assets(key)
        if assets:
            icon_path = assets.path("device_small")
            if icon_path.is_file():
                icon.setPixmap(
                    QPixmap(str(icon_path)).scaled(
                        18,
                        18,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        row.addWidget(icon)
        text = QLabel(f"{label}: Not detected")
        text.setObjectName("footerDeviceText")
        row.addWidget(text)
        return container

    def set_device_statuses(self, vita: str, three_ds: str, ds: str) -> None:
        values = {"vita": vita, "3ds": three_ds, "ds": ds}
        for key, text in values.items():
            widget = self.footer_devices.get(key)
            if widget is None:
                continue
            labels = widget.findChildren(QLabel)
            if labels:
                prefix = {"vita": "Vita", "3ds": "3DS", "ds": "DS"}[key]
                labels[-1].setText(f"{prefix}: {text}")

    def _load_logo(self) -> None:
        assets = get_platform_assets(self.profile.key)
        if not assets:
            self.logo.clear()
            return
        logo_path = assets.path("logo_dark")
        if not logo_path.is_file():
            self.logo.clear()
            return
        self.logo.setPixmap(
            QPixmap(str(logo_path)).scaled(
                145,
                42,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def set_profile(self, profile: WorkspaceProfile) -> None:
        self.profile = profile
        self.title.setText(profile.name.upper())
        self.footer_section.setText(
            f"{profile.name} • {self.tabs.tabText(self.tabs.currentIndex()).upper() if self.tabs.count() else 'READY'}"
        )
        self._load_logo()
        self.setStyleSheet(self._stylesheet())

    def clear_sections(self) -> None:
        while self.tabs.count():
            widget = self.tabs.widget(0)
            self.tabs.removeTab(0)
            if widget is not None:
                widget.setParent(None)
                if widget.objectName() != "persistentLibrary":
                    widget.deleteLater()

    def add_section(self, name: str, widget: QWidget, persistent: bool = False) -> None:
        if persistent:
            widget.setObjectName("persistentLibrary")
        self.tabs.addTab(widget, name.upper())

    def select_section(self, section: str) -> None:
        wanted = section.upper()
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == wanted:
                self.tabs.setCurrentIndex(index)
                return

    def _tab_changed(self, index: int) -> None:
        if index < 0:
            return
        section = self.tabs.tabText(index).lower()
        self.footer_section.setText(f"{self.profile.name} • {section.upper()}")
        self.navigation_requested.emit(section)

    def _stylesheet(self) -> str:
        p = self.profile
        return f"""
        QWidget#managementShell {{ background:#0a0d12; color:#eef1f5; }}
        QFrame#workspaceHeader {{ background:{p.secondary}; border:2px solid {p.accent}; border-radius:16px; }}
        QLabel#workspaceTitle {{ color:{p.accent}; font-size:20px; font-weight:900; letter-spacing:2px; }}
        QLabel#workspaceSubtitle {{ color:#abb4c0; font-size:11px; }}
        QPushButton#changeButton {{ background:transparent; border:1px solid {p.accent}; color:#eef1f5; padding:7px 11px; border-radius:8px; font-weight:800; }}
        QPushButton#changeButton:hover {{ background:{p.accent}; color:#081019; }}
        QTabWidget#workspaceTabs::pane {{ background:#0f1319; border:1px solid #292f38; border-radius:0 0 14px 14px; top:-1px; }}
        QTabBar::tab {{ background:#12161c; color:#9da6b2; border:1px solid #292f38; border-bottom:none; padding:9px 16px; margin-right:3px; border-radius:8px 8px 0 0; font-weight:800; }}
        QTabBar::tab:hover {{ color:#ffffff; border-color:{p.accent}; }}
        QTabBar::tab:selected {{ background:#171d26; color:{p.accent}; border-color:{p.accent}; }}
        QFrame#workspaceFooter {{ background:#12161c; border-top:2px solid {p.accent}; }}
        QLabel#footerSection {{ color:#b7c0ca; font-size:10px; font-weight:800; }}
        QLabel#footerDeviceText {{ color:#aab3bf; font-size:10px; }}
        """
