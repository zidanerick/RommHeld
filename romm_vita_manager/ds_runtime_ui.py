from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .design_tokens import DARK
from .ds_repair import DsRepairAction
from .ds_runtime import DsHealthCheck, DsHealthReport
from .ui_components import (
    ComponentHealthRow,
    HealthNotice,
    HealthSummaryCard,
    OperationStatusPanel,
    RepairPlanReviewDialog,
    SurfaceCard,
)


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
    a supplied report plus the repair actions supplied by ``ds_repair``. Safe
    actions are reviewed before their identifier is emitted to the Device page;
    guided/manual actions remain informational and never become automatic writes.
    """

    action_requested = Signal(str)

    def __init__(self, accent: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._accent = accent
        self._rows: dict[str, ComponentHealthRow] = {}
        self._actions: dict[str, DsRepairAction] = {}
        self._ordered_actions: tuple[DsRepairAction, ...] = ()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.summary = HealthSummaryCard(
            "Nintendo DS / DSi readiness",
            "unknown",
            "Select removable storage to inspect runtime readiness.",
            accent,
        )
        self.summary.action_requested.connect(self._handle_action)
        layout.addWidget(self.summary)

        self.components = SurfaceCard()
        title = QLabel("Runtime components")
        title.setStyleSheet(
            f"color:{DARK.text_primary};font-size:15px;font-weight:700;background:transparent;"
        )
        self.components.content.addWidget(title)
        description = QLabel(
            "Filesystem evidence is shown separately from operational proof. Expand Evidence for the exact paths/version markers supplied by the DS runtime service."
        )
        description.setWordWrap(True)
        description.setStyleSheet(f"color:{DARK.text_secondary};background:transparent;")
        self.components.content.addWidget(description)
        self.component_container = QWidget()
        self.component_layout = QVBoxLayout(self.component_container)
        self.component_layout.setContentsMargins(0, 0, 0, 0)
        self.component_layout.setSpacing(0)
        self.components.content.addWidget(self.component_container)
        layout.addWidget(self.components)
        self.components.setVisible(False)

        self.notice_container = QWidget()
        self.notice_layout = QVBoxLayout(self.notice_container)
        self.notice_layout.setContentsMargins(0, 0, 0, 0)
        self.notice_layout.setSpacing(8)
        self.notice_container.setVisible(False)
        layout.addWidget(self.notice_container)

        self.operation = OperationStatusPanel(
            "DS setup activity",
            "unknown",
            "No setup action has run.",
            accent,
            state_label="Idle",
        )
        self.operation.setVisible(False)
        layout.addWidget(self.operation)

    def set_unavailable(self, summary: str) -> None:
        self._clear_rows()
        self._clear_notices()
        self._actions.clear()
        self._ordered_actions = ()
        self.summary.set_state("unknown", label="Not checked", summary=summary, detail="")
        self.summary.set_primary_action("", "")
        self.summary.set_secondary_action("", "")
        self.components.setVisible(False)
        self.notice_container.setVisible(False)
        self.operation.setVisible(False)

    def set_error(self, summary: str) -> None:
        self._clear_rows()
        self._clear_notices()
        self._actions.clear()
        self._ordered_actions = ()
        self.summary.set_state("error", summary=summary, detail="")
        self.summary.set_primary_action("", "")
        self.summary.set_secondary_action("", "")
        self.components.setVisible(False)
        self.notice_container.setVisible(False)

    def set_report(
        self,
        report: DsHealthReport,
        actions: tuple[DsRepairAction, ...],
    ) -> None:
        self._clear_rows()
        self._clear_notices()
        self._ordered_actions = tuple(actions)
        self._actions = {action.key: action for action in actions}
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

        primary = next((action for action in actions if action.key != "defer-3ds"), None)
        if primary is not None:
            self.summary.set_primary_action(primary.key, primary.label)
        defer = next((action for action in actions if action.key == "defer-3ds"), None)
        if defer is not None:
            self.summary.set_secondary_action(defer.key, defer.label)

        action_by_component: dict[str, DsRepairAction] = {}
        for action in actions:
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
            row.action_requested.connect(self._handle_action)
            self.component_layout.addWidget(row)
            self._rows[check.key] = row

        manual_actions = tuple(action for action in actions if action.scope == "manual")
        for action in manual_actions:
            self.notice_layout.addWidget(
                HealthNotice(
                    action.label,
                    action.description,
                )
            )
        self.notice_container.setVisible(bool(manual_actions))
        self.components.setVisible(bool(self._rows))

    def row(self, key: str) -> ComponentHealthRow:
        return self._rows[key]

    def set_operation(
        self,
        state: str,
        summary: str,
        *,
        label: str | None = None,
        detail: str = "",
    ) -> None:
        self.operation.set_state(state, summary, label=label, detail=detail)
        self.operation.setVisible(True)

    def clear_operation(self) -> None:
        self.operation.setVisible(False)

    def _handle_action(self, action_id: str) -> None:
        action = self._actions.get(action_id)
        if action is None:
            return
        if action.key == "defer-3ds":
            self.action_requested.emit(action.key)
            return
        if action.scope == "safe":
            if self._review_safe_plan(action):
                self.action_requested.emit(action.key)
            return
        self._show_guided_action(action)

    def _review_safe_plan(self, selected: DsRepairAction) -> bool:
        steps = tuple(
            f"{action.label} [{action.scope}] · {action.description}"
            for action in self._ordered_actions
        )
        warnings = tuple(
            f"{action.label}: {action.description}"
            for action in self._ordered_actions
            if action.scope == "manual"
        )
        dialog = RepairPlanReviewDialog(
            "Review DS setup plan",
            "Only the selected service action marked safe will be applied automatically. Guided and manual steps remain unchanged.",
            steps,
            warnings=warnings,
            confirm_label=selected.label,
            accent=self._accent,
            parent=self,
        )
        return dialog.exec() == dialog.DialogCode.Accepted

    def _show_guided_action(self, action: DsRepairAction) -> None:
        warnings = (
            (action.description,)
            if action.scope == "manual"
            else ()
        )
        dialog = RepairPlanReviewDialog(
            action.label,
            "This service action is not an automatic RommHeld repair.",
            (action.description,),
            warnings=warnings,
            confirm_label="Close",
            accent=self._accent,
            parent=self,
        )
        dialog.exec()

    def _clear_rows(self) -> None:
        for row in self._rows.values():
            self.component_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

    def _clear_notices(self) -> None:
        while self.notice_layout.count():
            item = self.notice_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()


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
