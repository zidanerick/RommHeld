from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .design_tokens import (
    BRANDS,
    DARK,
    health_state_label,
    health_state_tone,
    status_tone,
)


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
        # Qt treats a single ampersand in button text as a mnemonic marker.
        # RommHeld uses explicit keyboard focus rather than Alt-key mnemonics,
        # so display product copy literally (for example, "Readiness & Runtimes").
        super().__init__(text.replace("&", "&&"), parent)
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


class HealthStateBadge(QFrame):
    """Compact rendering of an explicit health state supplied by a service."""

    def __init__(
        self,
        state: str = "unknown",
        label: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("healthStateBadge")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 3, 8, 3)
        row.setSpacing(0)
        self.label = QLabel()
        self.label.setObjectName("healthStateBadgeLabel")
        row.addWidget(self.label)
        self.set_state(state, label)

    def set_state(self, state: str, label: str | None = None) -> None:
        tone = health_state_tone(state)
        color = _status_tone_color(tone)
        self.setProperty("healthState", state)
        self.setProperty("healthTone", tone)
        self.label.setText(health_state_label(state, label))
        self.setStyleSheet(
            f"""
            QFrame#healthStateBadge {{
                background:{DARK.surface_raised};
                border:1px solid {color};
                border-radius:8px;
            }}
            QLabel#healthStateBadgeLabel {{
                color:{color};
                background:transparent;
                border:none;
                font-size:10px;
                font-weight:700;
            }}
            """
        )


class EvidenceDisclosure(QWidget):
    """Progressive disclosure for service-supplied evidence and diagnostics."""

    def __init__(
        self,
        text: str = "",
        label: str = "Evidence",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setChecked(False)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle.setStyleSheet(
            f"""
            QToolButton {{
                background:transparent;
                color:{DARK.text_secondary};
                border:1px solid transparent;
                border-radius:8px;
                padding:5px 7px;
                font-weight:600;
            }}
            QToolButton:hover {{
                background:{DARK.surface_hover};
                color:{DARK.text_primary};
            }}
            QToolButton:focus {{
                border-color:{DARK.text_primary};
            }}
            """
        )

        self.details = QFrame()
        self.details.setObjectName("healthEvidenceDetails")
        self.details.setStyleSheet(
            f"QFrame#healthEvidenceDetails{{background:{DARK.surface_raised};border:none;border-radius:8px;}}"
        )
        detail_layout = QVBoxLayout(self.details)
        detail_layout.setContentsMargins(10, 8, 10, 8)
        detail_layout.setSpacing(0)
        self.detail_label = QLabel()
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail_label.setStyleSheet(f"color:{DARK.text_secondary};background:transparent;")
        detail_layout.addWidget(self.detail_label)

        layout.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.details)
        self.toggle.toggled.connect(self._set_expanded)
        self.set_details(text, label)

    def set_details(self, text: str, label: str = "Evidence") -> None:
        self.detail_label.setText(text)
        self.toggle.setText(label)
        has_details = bool(text.strip())
        self.toggle.setVisible(has_details)
        if not has_details:
            self.toggle.setChecked(False)
        self.details.setVisible(has_details and self.toggle.isChecked())

    def set_expanded(self, expanded: bool) -> None:
        self.toggle.setChecked(bool(expanded) and self.toggle.isVisible())

    def _set_expanded(self, expanded: bool) -> None:
        self.toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.details.setVisible(expanded and bool(self.detail_label.text().strip()))


class HealthSummaryCard(SurfaceCard):
    """Overall health summary whose state and actions are supplied externally."""

    action_requested = Signal(str)

    def __init__(
        self,
        title: str,
        state: str,
        summary: str,
        accent: str,
        *,
        state_label: str | None = None,
        detail: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        header = QHBoxLayout()
        header.setSpacing(10)
        self.title = QLabel(title)
        self.title.setWordWrap(True)
        self.title.setStyleSheet(
            f"color:{DARK.text_primary};font-size:15px;font-weight:700;background:transparent;"
        )
        self.badge = HealthStateBadge(state, state_label)
        header.addWidget(self.title, 1)
        header.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop)
        self.content.addLayout(header)

        self.summary = QLabel(summary)
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.summary.setStyleSheet(f"color:{DARK.text_primary};background:transparent;")
        self.content.addWidget(self.summary)

        self.detail = QLabel(detail)
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail.setStyleSheet(f"color:{DARK.text_secondary};background:transparent;")
        self.detail.setVisible(bool(detail))
        self.content.addWidget(self.detail)

        self._primary_action_id = ""
        self._secondary_action_id = ""
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        self.secondary_action = QPushButton()
        self.secondary_action.setVisible(False)
        self.secondary_action.clicked.connect(self._emit_secondary_action)
        self.primary_action = AccentButton("", accent)
        self.primary_action.setVisible(False)
        self.primary_action.clicked.connect(self._emit_primary_action)
        self.actions.addWidget(self.secondary_action)
        self.actions.addStretch(1)
        self.actions.addWidget(self.primary_action)
        self.content.addLayout(self.actions)

    def set_state(
        self,
        state: str,
        *,
        label: str | None = None,
        summary: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.badge.set_state(state, label)
        if summary is not None:
            self.summary.setText(summary)
        if detail is not None:
            self.detail.setText(detail)
            self.detail.setVisible(bool(detail))

    def set_primary_action(self, action_id: str, label: str) -> None:
        self._primary_action_id = action_id
        self.primary_action.setText(label.replace("&", "&&"))
        self.primary_action.setVisible(bool(action_id and label))

    def set_secondary_action(self, action_id: str, label: str) -> None:
        self._secondary_action_id = action_id
        self.secondary_action.setText(label)
        self.secondary_action.setVisible(bool(action_id and label))

    def _emit_primary_action(self) -> None:
        if self._primary_action_id:
            self.action_requested.emit(self._primary_action_id)

    def _emit_secondary_action(self) -> None:
        if self._secondary_action_id:
            self.action_requested.emit(self._secondary_action_id)


class ComponentHealthRow(QFrame):
    """Compact component health row for grouping inside one Device surface."""

    action_requested = Signal(str)

    def __init__(
        self,
        title: str,
        state: str,
        summary: str,
        accent: str,
        *,
        state_label: str | None = None,
        evidence: str = "",
        evidence_label: str = "Evidence",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("componentHealthRow")
        self.setStyleSheet(
            f"QFrame#componentHealthRow{{background:transparent;border:none;border-bottom:1px solid {DARK.separator};}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 12)
        layout.setSpacing(7)

        header = QHBoxLayout()
        header.setSpacing(10)
        self.title = QLabel(title)
        self.title.setWordWrap(True)
        self.title.setStyleSheet(
            f"color:{DARK.text_primary};font-size:13px;font-weight:700;background:transparent;"
        )
        self.badge = HealthStateBadge(state, state_label)
        header.addWidget(self.title, 1)
        header.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        self.summary = QLabel(summary)
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.summary.setStyleSheet(f"color:{DARK.text_secondary};background:transparent;")
        layout.addWidget(self.summary)

        self.evidence = EvidenceDisclosure(evidence, evidence_label)
        layout.addWidget(self.evidence)

        self._action_id = ""
        action_row = QHBoxLayout()
        action_row.addStretch(1)
        self.action = AccentButton("", accent)
        self.action.set_emphasized(False)
        self.action.setVisible(False)
        self.action.clicked.connect(self._emit_action)
        action_row.addWidget(self.action)
        layout.addLayout(action_row)

    def set_state(
        self,
        state: str,
        *,
        label: str | None = None,
        summary: str | None = None,
    ) -> None:
        self.badge.set_state(state, label)
        if summary is not None:
            self.summary.setText(summary)

    def set_evidence(self, text: str, label: str = "Evidence") -> None:
        self.evidence.set_details(text, label)

    def set_action(
        self,
        action_id: str,
        label: str,
        *,
        emphasized: bool = False,
    ) -> None:
        self._action_id = action_id
        self.action.setText(label.replace("&", "&&"))
        self.action.setVisible(bool(action_id and label))
        self.action.set_emphasized(emphasized)

    def _emit_action(self) -> None:
        if self._action_id:
            self.action_requested.emit(self._action_id)


class WorkflowReadinessRow(ComponentHealthRow):
    """Presentation-only row for service-supplied workflow readiness."""


class HealthNotice(QFrame):
    """Warning surface for manual-only or system-sensitive service states."""

    action_requested = Signal(str)

    def __init__(
        self,
        title: str,
        text: str,
        *,
        action_id: str = "",
        action_label: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("healthNotice")
        self.setStyleSheet(
            f"QFrame#healthNotice{{background:{DARK.surface_raised};border:1px solid {DARK.warning};border-radius:10px;}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        self.title = QLabel(title)
        self.title.setWordWrap(True)
        self.title.setStyleSheet(
            f"color:{DARK.warning};font-weight:700;background:transparent;"
        )
        self.text = QLabel(text)
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.text.setStyleSheet(f"color:{DARK.text_secondary};background:transparent;")
        layout.addWidget(self.title)
        layout.addWidget(self.text)

        self._action_id = action_id
        self.action = QPushButton(action_label)
        self.action.setVisible(bool(action_id and action_label))
        self.action.clicked.connect(self._emit_action)
        action_row = QHBoxLayout()
        action_row.addStretch(1)
        action_row.addWidget(self.action)
        layout.addLayout(action_row)

    def set_action(self, action_id: str, label: str) -> None:
        self._action_id = action_id
        self.action.setText(label)
        self.action.setVisible(bool(action_id and label))

    def _emit_action(self) -> None:
        if self._action_id:
            self.action_requested.emit(self._action_id)


class RepairPlanReviewDialog(QDialog):
    """Review a service-supplied repair plan before the caller executes it."""

    def __init__(
        self,
        title: str,
        summary: str,
        steps: tuple[str, ...] | list[str],
        *,
        warnings: tuple[str, ...] | list[str] = (),
        confirm_label: str = "Apply repair",
        accent: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Review repair plan")
        self.resize(680, 520)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        root.addWidget(SectionHeader(title, summary))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 4, 0)
        body_layout.setSpacing(10)

        if steps:
            heading = QLabel("Planned changes")
            heading.setStyleSheet(
                f"color:{DARK.text_primary};font-weight:700;background:transparent;"
            )
            body_layout.addWidget(heading)
            for index, step in enumerate(steps, 1):
                label = QLabel(f"{index}. {step}")
                label.setWordWrap(True)
                label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                label.setStyleSheet(f"color:{DARK.text_secondary};background:transparent;")
                body_layout.addWidget(label)

        for warning in warnings:
            notice = HealthNotice("Review before continuing", warning)
            body_layout.addWidget(notice)

        body_layout.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        self.confirm_button = AccentButton(
            confirm_label,
            accent or BRANDS["neutral"].accent,
        )
        self.confirm_button.clicked.connect(self.accept)
        buttons.addButton(self.confirm_button, QDialogButtonBox.ButtonRole.AcceptRole)
        root.addWidget(buttons)


class OperationStatusPanel(QFrame):
    """Inline progress/failure presentation for an externally owned operation."""

    action_requested = Signal(str)

    def __init__(
        self,
        title: str,
        state: str,
        summary: str,
        accent: str,
        *,
        detail: str = "",
        state_label: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("operationStatusPanel")
        self.setStyleSheet(
            f"QFrame#operationStatusPanel{{background:{DARK.surface_raised};border:1px solid {DARK.separator};border-radius:10px;}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)

        header = QHBoxLayout()
        self.title = QLabel(title)
        self.title.setWordWrap(True)
        self.title.setStyleSheet(
            f"color:{DARK.text_primary};font-weight:700;background:transparent;"
        )
        self.badge = HealthStateBadge(state, state_label)
        header.addWidget(self.title, 1)
        header.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        self.summary = QLabel(summary)
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.summary.setStyleSheet(f"color:{DARK.text_secondary};background:transparent;")
        layout.addWidget(self.summary)

        self.detail = QLabel(detail)
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail.setStyleSheet(f"color:{DARK.text_tertiary};background:transparent;")
        self.detail.setVisible(bool(detail))
        layout.addWidget(self.detail)

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self._primary_action_id = ""
        self._secondary_action_id = ""
        action_row = QHBoxLayout()
        self.secondary_action = QPushButton()
        self.secondary_action.setVisible(False)
        self.secondary_action.clicked.connect(self._emit_secondary_action)
        self.primary_action = AccentButton("", accent)
        self.primary_action.setVisible(False)
        self.primary_action.clicked.connect(self._emit_primary_action)
        action_row.addWidget(self.secondary_action)
        action_row.addStretch(1)
        action_row.addWidget(self.primary_action)
        layout.addLayout(action_row)

    def set_state(
        self,
        state: str,
        summary: str,
        *,
        label: str | None = None,
        detail: str = "",
        progress: int | None = None,
        indeterminate: bool = False,
    ) -> None:
        self.badge.set_state(state, label)
        self.summary.setText(summary)
        self.detail.setText(detail)
        self.detail.setVisible(bool(detail))
        if indeterminate:
            self.progress.setRange(0, 0)
            self.progress.setVisible(True)
        elif progress is not None:
            self.progress.setRange(0, 100)
            self.progress.setValue(max(0, min(100, int(progress))))
            self.progress.setVisible(True)
        else:
            self.progress.setVisible(False)

    def set_primary_action(self, action_id: str, label: str) -> None:
        self._primary_action_id = action_id
        self.primary_action.setText(label.replace("&", "&&"))
        self.primary_action.setVisible(bool(action_id and label))

    def set_secondary_action(self, action_id: str, label: str) -> None:
        self._secondary_action_id = action_id
        self.secondary_action.setText(label)
        self.secondary_action.setVisible(bool(action_id and label))

    def _emit_primary_action(self) -> None:
        if self._primary_action_id:
            self.action_requested.emit(self._primary_action_id)

    def _emit_secondary_action(self) -> None:
        if self._secondary_action_id:
            self.action_requested.emit(self._secondary_action_id)


__all__ = [
    "AccentButton",
    "ComponentHealthRow",
    "EvidenceDisclosure",
    "HealthNotice",
    "HealthStateBadge",
    "HealthSummaryCard",
    "OperationStatusPanel",
    "RepairPlanReviewDialog",
    "SectionHeader",
    "StatusPill",
    "SurfaceCard",
    "WorkflowReadinessRow",
]