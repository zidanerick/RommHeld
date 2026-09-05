from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .design_tokens import DARK, status_tone


def _status_tone_color(tone: str) -> str:
    return {
        "success": DARK.success,
        "warning": DARK.warning,
        "error": DARK.error,
        "muted": DARK.text_tertiary,
        "neutral": DARK.text_primary,
    }.get(tone, DARK.text_primary)


class SectionHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self.title = QLabel(title)
        self.title.setObjectName("sectionTitle")
        self.title.setStyleSheet(
            f"color:{DARK.text_primary};font-size:22px;font-weight:700;background:transparent;"
        )
        layout.addWidget(self.title)

        self.subtitle = QLabel(subtitle)
        self.subtitle.setProperty("secondary", True)
        self.subtitle.setWordWrap(True)
        self.subtitle.setVisible(bool(subtitle))
        layout.addWidget(self.subtitle)

    def set_subtitle(self, text: str) -> None:
        self.subtitle.setText(text)
        self.subtitle.setVisible(bool(text))


class SurfaceCard(QFrame):
    """Neutral reusable content card with consistent spacing and radius."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("surfaceCard")
        self.setStyleSheet(
            f"QFrame#surfaceCard{{background:{DARK.surface};border:1px solid {DARK.separator};border-radius:14px;}}"
        )
        self.content = QVBoxLayout(self)
        self.content.setContentsMargins(16, 16, 16, 16)
        self.content.setSpacing(10)


class StatusPill(QFrame):
    def __init__(self, label: str, value: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("statusPill")
        self.setStyleSheet(
            f"QFrame#statusPill{{background:{DARK.surface};border:1px solid {DARK.separator};border-radius:9px;}}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(5)
        self.label = QLabel(label)
        self.label.setProperty("secondary", True)
        self.value = QLabel()
        row.addWidget(self.label)
        row.addWidget(self.value)
        self.set_value(value)

    def set_value(self, value: str, tone: str | None = None) -> None:
        self.value.setText(value)
        resolved_tone = tone or status_tone(value)
        self.value.setStyleSheet(
            f"color:{_status_tone_color(resolved_tone)};font-weight:600;background:transparent;"
        )


class AccentButton(QPushButton):
    def __init__(self, text: str, accent: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self._accent = accent
        self._emphasized = True
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_accent_style()

    def set_accent(self, accent: str) -> None:
        self._accent = accent
        if self._emphasized:
            self._apply_accent_style()

    def set_emphasized(self, emphasized: bool) -> None:
        """Toggle primary-action emphasis while retaining normal button behavior."""
        self._emphasized = bool(emphasized)
        if self._emphasized:
            self._apply_accent_style()
        else:
            # Clearing the local stylesheet restores the shared neutral button
            # styling from the application theme without replacing the widget.
            self.setStyleSheet("")

    def _apply_accent_style(self) -> None:
        accent = self._accent
        base = QColor(accent)
        hover = base.lighter(112).name() if base.isValid() else accent
        pressed = base.darker(112).name() if base.isValid() else accent
        self.setStyleSheet(
            f"""
            QPushButton {{
                background:{accent};
                color:#FFFFFF;
                border:1px solid transparent;
                border-radius:9px;
                padding:8px 14px;
                min-height:22px;
                font-weight:700;
            }}
            QPushButton:hover {{
                background:{hover};
                border-color:transparent;
            }}
            QPushButton:focus {{
                border-color:#FFFFFF;
            }}
            QPushButton:pressed {{
                background:{pressed};
                padding-top:9px;
                padding-bottom:7px;
            }}
            QPushButton:disabled {{
                background:#343437;
                color:#77777C;
                border-color:transparent;
            }}
            """
        )


__all__ = ["AccentButton", "SectionHeader", "StatusPill", "SurfaceCard"]