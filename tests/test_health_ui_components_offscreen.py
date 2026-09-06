from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from romm_vita_manager.design_tokens import (
    brand_for_platform,
    health_state_label,
    health_state_tone,
    normalize_health_state,
)
from romm_vita_manager.ui_components import (
    ComponentHealthRow,
    EvidenceDisclosure,
    HealthNotice,
    HealthSummaryCard,
    OperationStatusPanel,
    RepairPlanReviewDialog,
    WorkflowReadinessRow,
)


_APP: QApplication | None = None


def _app() -> QApplication:
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
    return _APP


def test_explicit_health_states_have_stable_presentation_semantics() -> None:
    assert normalize_health_state("assets-only") == "assets_only"
    assert normalize_health_state("unknown/manual-only") == "unknown_manual_only"
    assert health_state_tone("healthy") == "success"
    assert health_state_tone("partial") == "warning"
    assert health_state_tone("assets_only") == "warning"
    assert health_state_tone("repairable") == "warning"
    assert health_state_tone("manual-only") == "warning"
    assert health_state_tone("misconfigured") == "error"
    assert health_state_tone("missing") == "muted"
    assert health_state_tone("unknown") == "muted"
    assert health_state_tone("future_service_state") == "neutral"
    assert health_state_label("future_service_state") == "Future Service State"


def test_health_summary_emits_only_the_service_supplied_action_id() -> None:
    _app()
    summary = HealthSummaryCard(
        "Device health",
        "repairable",
        "Two service-reported components need attention.",
        brand_for_platform("3ds").accent,
    )
    summary.set_primary_action("repair_runtime", "Repair")
    summary.set_secondary_action("verify_again", "Verify again")
    emitted: list[str] = []
    summary.action_requested.connect(emitted.append)

    summary.primary_action.click()
    summary.secondary_action.click()

    assert emitted == ["repair_runtime", "verify_again"]
    assert summary.badge.label.text() == "Repairable"


def test_component_evidence_is_progressively_disclosed_and_keyboard_focusable() -> None:
    _app()
    row = ComponentHealthRow(
        "Runtime assets",
        "partial",
        "The service found only part of the expected installation.",
        brand_for_platform("ds").accent,
        evidence=(
            "Found frontend assets under a very long service-supplied path. "
            "The service also reported that bootstrap evidence is incomplete."
        ),
    )

    assert row.summary.wordWrap()
    assert row.evidence.toggle.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert row.evidence.details.isHidden()

    row.evidence.toggle.click()

    assert row.evidence.toggle.isChecked()
    assert not row.evidence.details.isHidden()
    assert row.evidence.detail_label.wordWrap()
    assert "bootstrap evidence" in row.evidence.detail_label.text()


def test_component_action_can_be_quiet_or_explicitly_emphasized() -> None:
    _app()
    row = ComponentHealthRow(
        "Component",
        "repairable",
        "Repair is available according to the service.",
        brand_for_platform("vita").accent,
    )
    emitted: list[str] = []
    row.action_requested.connect(emitted.append)

    row.set_action("repair_component", "Repair", emphasized=False)
    assert not row.action._emphasized
    row.action.click()

    row.set_action("complete_setup", "Complete setup", emphasized=True)
    assert row.action._emphasized
    row.action.click()

    assert emitted == ["repair_component", "complete_setup"]


def test_manual_only_notice_keeps_guide_action_external() -> None:
    _app()
    notice = HealthNotice(
        "System-sensitive component",
        "Automatic changes are not offered for this service-reported state.",
        action_id="open_guide",
        action_label="Open guide",
    )
    emitted: list[str] = []
    notice.action_requested.connect(emitted.append)

    notice.action.click()

    assert emitted == ["open_guide"]
    assert notice.text.wordWrap()


def test_repair_plan_dialog_reviews_supplied_changes_before_acceptance() -> None:
    _app()
    dialog = RepairPlanReviewDialog(
        "Review runtime repair",
        "The device service supplied the following repair plan.",
        [
            "Back up the current configuration file.",
            "Replace the incomplete runtime assets with verified files.",
            "Re-run verification after the write completes.",
        ],
        warnings=[
            "This plan changes files on removable storage. Review the destination before continuing."
        ],
        confirm_label="Apply repair",
        accent=brand_for_platform("3ds").accent,
    )

    assert dialog.result() == 0
    assert dialog.confirm_button.text() == "Apply repair"
    dialog.confirm_button.click()
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_operation_status_panel_handles_progress_failure_and_retry_presentation() -> None:
    _app()
    panel = OperationStatusPanel(
        "Repair runtime",
        "busy",
        "Preparing verified files…",
        brand_for_platform("3ds").accent,
    )
    panel.set_state(
        "busy",
        "Preparing verified files…",
        detail="Checking package integrity before changes.",
        indeterminate=True,
    )
    assert panel.progress.isVisibleTo(panel)
    assert panel.progress.minimum() == 0
    assert panel.progress.maximum() == 0

    panel.set_state(
        "failed",
        "Repair stopped before replacement completed.",
        detail="The service reported a write failure and preserved the existing files.",
    )
    panel.set_primary_action("retry_repair", "Retry")
    panel.set_secondary_action("open_details", "Show details")
    emitted: list[str] = []
    panel.action_requested.connect(emitted.append)
    panel.primary_action.click()
    panel.secondary_action.click()

    assert panel.badge.label.text() == "Failed"
    assert panel.progress.isHidden()
    assert emitted == ["retry_repair", "open_details"]


def test_workflow_readiness_rows_render_arbitrary_service_results_without_rules() -> None:
    _app()
    accent = brand_for_platform("3ds").accent
    gba = WorkflowReadinessRow(
        "GBA ready",
        "ready",
        "The runtime service reports this workflow ready.",
        accent,
    )
    nds = WorkflowReadinessRow(
        "NDS ready",
        "ready",
        "The runtime service reports this workflow ready.",
        accent,
    )
    achievements = WorkflowReadinessRow(
        "RetroAchievements route",
        "incomplete",
        "The runtime service reports that this route is incomplete.",
        accent,
    )

    assert gba.title.text() == "GBA ready"
    assert gba.badge.label.text() == "Ready"
    assert nds.title.text() == "NDS ready"
    assert nds.badge.label.text() == "Ready"
    assert achievements.title.text() == "RetroAchievements route"
    assert achievements.badge.label.text() == "Incomplete"


def test_health_components_wrap_long_native_desktop_copy_at_compact_width() -> None:
    app = _app()
    disclosure = EvidenceDisclosure(
        "Evidence may include long mounted-storage paths, package versions, marker names, "
        "and service diagnostics. These details must wrap rather than force the Device page wider."
    )
    disclosure.resize(520, 180)
    disclosure.show()
    disclosure.set_expanded(True)
    app.processEvents()

    assert disclosure.detail_label.wordWrap()
    assert disclosure.width() == 520
    assert disclosure.detail_label.width() <= disclosure.width()

    disclosure.close()
    disclosure.deleteLater()
    app.processEvents()
