from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .design_tokens import DARK
from .ds_repair import DsRepairAction
from .ds_runtime import DsHealthCheck, DsHealthReport
from .ui_components import ComponentHealthRow, HealthSummaryCard, SurfaceCard


_COMPONENT_TITLES = {
    "storage": "Removable storage",
    "twilight-menu": "TWiLight Menu++",
    "nds-bootstrap": "nds-bootstrap",
    "launcher": "Launcher / bootstrap",
    "dsi-environment": "DSi homebrew / CFW state",
    "flashcart-kernel": "Flashcart kernel / runtime",
    "rom-directories": "Nintendo DS ROM directory",
    "save-directories": "Nintendo DS save directory",
    "config": "TWiLight configuration",
}

_ACTION_COMPONENTS = {
    "guide-twilight-menu": "twilight-menu",
    "guide-nds-bootstrap": "nds-bootstrap",
    "guide-launcher": "launcher",
    "repair-config": "config",
    "confirm-dsi-boot": "dsi-environment",
    "confirm-flashcart": "flashcart-kernel",
}


class DsRuntimeHealthPanel(QWidget):
    """Presentation-only DS/DSi health surface.

    The runtime service owns detection and health semantics. This widget renders
    a supplied report plus the repair actions supplied by ``ds_repair`` and
    emits action identifiers back to the owning Device page.
    """

    action_requested = Signal(str)

    def __init__(self, accent: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._accent = accent
        self._rows: dict[str, ComponentHealthRow] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.summary = HealthSummaryCard(
            "Nintendo DS / DSi readiness",
            "unknown",
            "Select removable storage to inspect runtime readiness.",
            accent,
        )
        self.summary.action_requested.connect(self.action_requested.emit)
        layout.addWidget(self.summary)

        self.components = SurfaceCard()
        title = QLabel("Runtime components")
        title.setStyleSheet(
            f"color:{DARK.text_primary};font-size:15px;font-weight:700;background:transparent;"
        )
        self.components.content.addWidget(title)
        self.component_container = QWidget()
        self.component_layout = QVBoxLayout(self.component_container)
        self.component_layout.setContentsMargins(0, 0, 0, 0)
        self.component_layout.setSpacing(0)
        self.components.content.addWidget(self.component_container)
        layout.addWidget(self.components)
        self.components.setVisible(False)

    def set_unavailable(self, summary: str) -> None:
        self._clear_rows()
        self.summary.set_state("unknown", summary=summary, detail="")
        self.summary.set_primary_action("", "")
        self.summary.set_secondary_action("", "")
        self.components.setVisible(False)

    def set_error(self, summary: str) -> None:
        self._clear_rows()
        self.summary.set_state("error", summary=summary, detail="")
        self.summary.set_primary_action("", "")
        self.summary.set_secondary_action("", "")
        self.components.setVisible(False)

    def set_report(
        self,
        report: DsHealthReport,
        actions: tuple[DsRepairAction, ...],
    ) -> None:
        self._clear_rows()
        detail_parts = [
            f"Environment: {report.profile.name} ({report.profile.confidence} confidence)"
        ]
        detail_parts.extend(report.notes)
        self.summary.set_state(
            report.overall_state,
            summary=report.summary,
            detail="\n".join(detail_parts),
        )
        self.summary.set_primary_action("", "")
        self.summary.set_secondary_action("", "")

        action_by_component: dict[str, DsRepairAction] = {}
        for action in actions:
            if action.key == "create-content-directories" and action.scope == "safe":
                self.summary.set_primary_action(action.key, action.label)
            elif action.key == "defer-3ds":
                self.summary.set_secondary_action(action.key, action.label)
            else:
                component_key = _ACTION_COMPONENTS.get(action.key)
                if component_key:
                    action_by_component[component_key] = action

        for check in report.checks:
            if check.state == "not_applicable":
                continue
            row = ComponentHealthRow(
                _COMPONENT_TITLES.get(check.key, check.key.replace("-", " ").title()),
                check.state,
                check.summary,
                self._accent,
                state_label=check.label,
                evidence=_evidence_text(check),
            )
            action = action_by_component.get(check.key)
            if action is not None:
                row.set_action(action.key, action.label, emphasized=False)
            row.action_requested.connect(self.action_requested.emit)
            self.component_layout.addWidget(row)
            self._rows[check.key] = row

        self.components.setVisible(bool(self._rows))

    def row(self, key: str) -> ComponentHealthRow:
        return self._rows[key]

    def _clear_rows(self) -> None:
        for row in self._rows.values():
            self.component_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()


def _evidence_text(check: DsHealthCheck) -> str:
    lines: list[str] = []
    if check.paths:
        lines.append("Observed:\n" + "\n".join(f"• {path}" for path in check.paths))
    if check.observed_version:
        lines.append(f"Observed version: {check.observed_version}")
    if check.known_version:
        lines.append(f"Known upstream baseline: {check.known_version}")
    return "\n\n".join(lines)


__all__ = ["DsRuntimeHealthPanel"]
