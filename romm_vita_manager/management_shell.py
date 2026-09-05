from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .design_tokens import DARK, SIDEBAR_WIDTH, brand_for_platform
from .platform_assets import get_platform_assets


@dataclass(frozen=True)
class WorkspaceProfile:
    key: str
    name: str
    accent: str
    secondary: str
    description: str


WORKSPACE_PROFILES = {
    "vita": WorkspaceProfile(
        "vita",
        "PlayStation Vita",
        brand_for_platform("vita").accent,
        brand_for_platform("vita").accent_soft,
        "VitaShell, RetroFlow and Adrenaline",
    ),
    "3ds": WorkspaceProfile(
        "3ds",
        "Nintendo 3DS",
        brand_for_platform("3ds").accent,
        brand_for_platform("3ds").accent_soft,
        "FTP, FBI Remote Install and native 3DS runtimes",
    ),
    "ds": WorkspaceProfile(
        "ds",
        "Nintendo DS",
        brand_for_platform("ds").accent,
        brand_for_platform("ds").accent_soft,
        "TWiLight Menu++, nds-bootstrap and flashcards",
    ),
}


class ManagementShell(QWidget):
    """Stable single-window shell with console branding and sidebar navigation.

    The public section API intentionally matches the previous tab shell so the
    device and library features can move into the new design without rewriting
    their business logic.
    """

    navigation_requested = Signal(str)
    change_handheld_requested = Signal()

    def __init__(self, profile: WorkspaceProfile, parent: QWidget | None = None):
        super().__init__(parent)
        self.profile = profile
        self._sections: dict[str, tuple[QPushButton, QWidget, str]] = {}
        self._device_values: dict[str, QLabel] = {}
        self._device_widgets: dict[str, QWidget] = {}

        self.setObjectName("managementShell")
        self.setStyleSheet(self._stylesheet())

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("workspaceSidebar")
        self.sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(16, 18, 16, 16)
        sidebar_layout.setSpacing(10)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(9)
        self.brand_mark = QLabel("RH")
        self.brand_mark.setObjectName("brandMark")
        self.brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_mark.setFixedSize(34, 34)
        brand_row.addWidget(self.brand_mark)
        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setSpacing(0)
        app_name = QLabel("RommHeld")
        app_name.setObjectName("appName")
        app_subtitle = QLabel("Handheld Library Manager")
        app_subtitle.setObjectName("appSubtitle")
        brand_text.addWidget(app_name)
        brand_text.addWidget(app_subtitle)
        brand_row.addLayout(brand_text, 1)
        sidebar_layout.addLayout(brand_row)

        self.console_card = QFrame()
        self.console_card.setObjectName("consoleCard")
        console_row = QHBoxLayout(self.console_card)
        console_row.setContentsMargins(10, 9, 10, 9)
        console_row.setSpacing(9)
        self.logo = QLabel()
        self.logo.setFixedSize(QSize(58, 34))
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        console_row.addWidget(self.logo)
        console_text = QVBoxLayout()
        console_text.setContentsMargins(0, 0, 0, 0)
        console_text.setSpacing(1)
        self.console_name = QLabel(profile.name)
        self.console_name.setObjectName("consoleName")
        self.console_family = QLabel("Active handheld")
        self.console_family.setObjectName("consoleFamily")
        console_text.addWidget(self.console_name)
        console_text.addWidget(self.console_family)
        console_row.addLayout(console_text, 1)
        sidebar_layout.addWidget(self.console_card)

        nav_heading = QLabel("WORKSPACE")
        nav_heading.setObjectName("sidebarHeading")
        sidebar_layout.addWidget(nav_heading)

        self.nav_host = QWidget()
        self.nav_host.setObjectName("navHost")
        self.nav_layout = QVBoxLayout(self.nav_host)
        self.nav_layout.setContentsMargins(0, 0, 0, 0)
        self.nav_layout.setSpacing(3)
        sidebar_layout.addWidget(self.nav_host)
        sidebar_layout.addStretch(1)

        device_heading = QLabel("DEVICE")
        device_heading.setObjectName("sidebarHeading")
        sidebar_layout.addWidget(device_heading)
        for key, label in (("vita", "Vita"), ("3ds", "Nintendo 3DS"), ("ds", "Nintendo DS")):
            widget = self._make_device_status(label, key)
            widget.setVisible(key == profile.key)
            self._device_widgets[key] = widget
            sidebar_layout.addWidget(widget)

        change = QPushButton("Switch handheld")
        change.setObjectName("changeButton")
        change.setProperty("quiet", True)
        change.clicked.connect(self.change_handheld_requested.emit)
        sidebar_layout.addWidget(change)
        root.addWidget(self.sidebar)

        self.content_root = QFrame()
        self.content_root.setObjectName("workspaceContent")
        self.content_root.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout = QVBoxLayout(self.content_root)
        content_layout.setContentsMargins(24, 20, 24, 24)
        content_layout.setSpacing(14)

        header = QFrame()
        header.setObjectName("workspaceHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(2, 0, 2, 4)
        header_layout.setSpacing(12)
        heading_layout = QVBoxLayout()
        heading_layout.setContentsMargins(0, 0, 0, 0)
        heading_layout.setSpacing(2)
        self.page_title = QLabel("Library")
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel(self._subtitle_for_section("library"))
        self.page_subtitle.setObjectName("pageSubtitle")
        heading_layout.addWidget(self.page_title)
        heading_layout.addWidget(self.page_subtitle)
        header_layout.addLayout(heading_layout, 1)

        self.accent_indicator = QFrame()
        self.accent_indicator.setObjectName("accentIndicator")
        self.accent_indicator.setFixedSize(42, 5)
        header_layout.addWidget(self.accent_indicator, 0, Qt.AlignmentFlag.AlignTop)
        content_layout.addWidget(header)

        self.stack = QStackedWidget()
        self.stack.setObjectName("workspaceStack")
        content_layout.addWidget(self.stack, 1)
        root.addWidget(self.content_root, 1)

        self._load_logo()

    def _make_device_status(self, label: str, key: str) -> QWidget:
        container = QFrame()
        container.setObjectName("deviceStatus")
        row = QHBoxLayout(container)
        row.setContentsMargins(7, 5, 7, 5)
        row.setSpacing(6)

        icon = QLabel()
        icon.setFixedSize(18, 18)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        assets = get_platform_assets(key)
        if assets:
            try:
                icon_path = assets.path("device_small")
            except ValueError:
                icon_path = None
            if icon_path and icon_path.is_file():
                icon.setPixmap(
                    QPixmap(str(icon_path)).scaled(
                        18,
                        18,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        row.addWidget(icon)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(0)
        name = QLabel(label)
        name.setObjectName("deviceName")
        value = QLabel("Not detected")
        value.setObjectName("deviceValue")
        text.addWidget(name)
        text.addWidget(value)
        row.addLayout(text, 1)
        self._device_values[key] = value
        return container

    def set_device_statuses(self, vita: str, three_ds: str, ds: str) -> None:
        values = {"vita": vita, "3ds": three_ds, "ds": ds}
        for key, text in values.items():
            value = self._device_values.get(key)
            if value is not None:
                value.setText(text)

    def _load_logo(self) -> None:
        assets = get_platform_assets(self.profile.key)
        if not assets:
            self.logo.clear()
            return
        for kind in ("logo_dark", "logo"):
            try:
                logo_path = assets.path(kind)
            except ValueError:
                continue
            if not logo_path.is_file():
                continue
            pixmap = QPixmap(str(logo_path))
            if pixmap.isNull():
                continue
            self.logo.setPixmap(
                pixmap.scaled(
                    56,
                    32,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            return
        self.logo.clear()

    def _subtitle_for_section(self, section: str) -> str:
        if section == "library":
            return f"Browse and deploy games for {self.profile.name}"
        if section == "device":
            return f"Connection, storage and transfer readiness for {self.profile.name}"
        if section == "setup":
            return f"Prepare {self.profile.name} software and connectivity"
        if section == "settings":
            return "Library source and deployment preferences"
        return self.profile.description

    def set_profile(self, profile: WorkspaceProfile) -> None:
        self.profile = profile
        self.console_name.setText(profile.name)
        self.page_subtitle.setText(self._subtitle_for_section("library"))
        for key, widget in self._device_widgets.items():
            widget.setVisible(key == profile.key)
        self._load_logo()
        self.setStyleSheet(self._stylesheet())
        for button, _widget, _display in self._sections.values():
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def clear_sections(self) -> None:
        for button, widget, _display in tuple(self._sections.values()):
            button.setParent(None)
            button.deleteLater()
            self.stack.removeWidget(widget)
            widget.setParent(None)
            if widget.objectName() != "persistentLibrary":
                widget.deleteLater()
        self._sections.clear()
        self.page_title.setText("Library")
        self.page_subtitle.setText(self._subtitle_for_section("library"))

    def add_section(self, name: str, widget: QWidget, persistent: bool = False) -> None:
        key = name.strip().lower()
        if key in {"queue", "tools"}:
            widget.setParent(None)
            widget.deleteLater()
            return
        if persistent:
            widget.setObjectName("persistentLibrary")

        button = QPushButton(name)
        button.setObjectName("navButton")
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _checked=False, section=key: self.select_section(section))
        self.nav_layout.addWidget(button)
        self.stack.addWidget(widget)
        self._sections[key] = (button, widget, name)

        if len(self._sections) == 1:
            self.select_section(key)

    def select_section(self, section: str) -> None:
        key = section.strip().lower()
        selected = self._sections.get(key)
        if selected is None:
            return

        selected_button, selected_widget, display = selected
        for button, _widget, _name in self._sections.values():
            button.setChecked(button is selected_button)
        self.stack.setCurrentWidget(selected_widget)
        self.page_title.setText(display)
        self.page_subtitle.setText(self._subtitle_for_section(key))
        self.navigation_requested.emit(key)

    def _stylesheet(self) -> str:
        p = self.profile
        return f"""
        QWidget#managementShell {{ background:{DARK.background}; color:{DARK.text_primary}; }}

        QFrame#workspaceSidebar {{
            background:{DARK.sidebar};
            border-right:1px solid #252528;
        }}
        QLabel#brandMark {{
            background:{p.accent};
            color:#ffffff;
            border-radius:9px;
            font-size:11px;
            font-weight:800;
        }}
        QLabel#appName {{ color:{DARK.text_primary}; font-size:16px; font-weight:700; }}
        QLabel#appSubtitle {{ color:{DARK.text_tertiary}; font-size:9px; }}

        QFrame#consoleCard {{
            background:{DARK.surface};
            border:1px solid {DARK.separator};
            border-radius:12px;
        }}
        QLabel#consoleName {{ color:{DARK.text_primary}; font-size:11px; font-weight:700; }}
        QLabel#consoleFamily {{ color:{p.accent}; font-size:9px; font-weight:600; }}
        QLabel#sidebarHeading {{
            color:{DARK.text_tertiary};
            font-size:9px;
            font-weight:700;
            letter-spacing:1px;
            padding:8px 6px 2px 6px;
        }}

        QPushButton#navButton {{
            background:transparent;
            color:{DARK.text_secondary};
            border:none;
            border-radius:9px;
            text-align:left;
            padding:8px 10px;
            font-weight:600;
        }}
        QPushButton#navButton:hover {{
            background:{DARK.surface};
            color:{DARK.text_primary};
            border:none;
        }}
        QPushButton#navButton:checked {{
            background:{p.secondary};
            color:{p.accent};
            border:none;
            font-weight:700;
        }}

        QFrame#deviceStatus {{
            background:transparent;
            border-radius:8px;
        }}
        QFrame#deviceStatus:hover {{ background:{DARK.surface}; }}
        QLabel#deviceName {{ color:{DARK.text_secondary}; font-size:9px; font-weight:600; }}
        QLabel#deviceValue {{ color:{DARK.text_tertiary}; font-size:9px; }}
        QPushButton#changeButton {{
            background:transparent;
            color:{DARK.text_secondary};
            border:1px solid {DARK.separator};
            border-radius:9px;
            padding:7px 10px;
            font-weight:600;
        }}
        QPushButton#changeButton:hover {{
            background:{DARK.surface};
            color:{DARK.text_primary};
            border-color:#4A4A4D;
        }}

        QFrame#workspaceContent {{ background:{DARK.background}; }}
        QFrame#workspaceHeader {{ background:transparent; border:none; }}
        QLabel#pageTitle {{ color:{DARK.text_primary}; font-size:25px; font-weight:700; }}
        QLabel#pageSubtitle {{ color:{DARK.text_secondary}; font-size:11px; }}
        QFrame#accentIndicator {{ background:{p.accent}; border-radius:2px; }}
        QStackedWidget#workspaceStack {{ background:transparent; border:none; }}
        """


__all__ = ["ManagementShell", "WORKSPACE_PROFILES", "WorkspaceProfile"]
