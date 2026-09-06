from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from romm_vita_manager.design_tokens import brand_for_platform
from romm_vita_manager.ds_repair import plan_ds_repairs
from romm_vita_manager.ds_runtime import inspect_ds_runtime
from romm_vita_manager.ds_runtime_ui import DsRuntimeHealthPanel


_APP: QApplication | None = None


def _app() -> QApplication:
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
    return _APP


def _twilight_fixture(root: Path) -> None:
    (root / "_nds" / "TWiLightMenu").mkdir(parents=True)
    (root / "_nds" / "nds-bootstrap-release.nds").write_bytes(b"nds")
    (root / "_nds" / "nds-bootstrap-release.ver").write_text(
        "nds-bootstrap v2.16.0\n", encoding="utf-8"
    )
    (root / "BOOT.NDS").write_bytes(b"boot")


def test_ds_health_panel_renders_service_report_and_safe_action(tmp_path: Path) -> None:
    _app()
    _twilight_fixture(tmp_path)
    report = inspect_ds_runtime(tmp_path)
    actions = plan_ds_repairs(report)
    panel = DsRuntimeHealthPanel(brand_for_platform("ds").accent)
    emitted: list[str] = []
    panel.action_requested.connect(emitted.append)

    panel.set_report(report, actions)

    assert panel.summary.badge.label.text() == "Present · Not verified"
    assert "Generic removable DS storage" in panel.summary.detail.text()
    assert panel.row("twilight-menu").badge.label.text() == "Present · Launch not verified"
    assert "nds-bootstrap-release.ver" in panel.row("nds-bootstrap").evidence.detail_label.text()
    assert panel.summary.primary_action.text() == "Create DS content/save directories"

    panel.summary.primary_action.click()
    assert emitted == ["create-content-directories"]


def test_ds_health_panel_exposes_dsi_manual_confirmation_without_flashcart_noise(tmp_path: Path) -> None:
    _app()
    _twilight_fixture(tmp_path)
    report = inspect_ds_runtime(tmp_path, profile_hint="dsi-homebrew")
    actions = plan_ds_repairs(report)
    panel = DsRuntimeHealthPanel(brand_for_platform("ds").accent)
    emitted: list[str] = []
    panel.action_requested.connect(emitted.append)

    panel.set_report(report, actions)

    assert "dsi-environment" in panel._rows
    assert "flashcart-kernel" not in panel._rows
    dsi = panel.row("dsi-environment")
    assert dsi.badge.label.text() == "Console confirmation required"
    assert dsi.action.text() == "Confirm DSi boot environment"

    dsi.action.click()
    assert emitted == ["confirm-dsi-boot"]


def test_ds_health_panel_deferred_3ds_media_exposes_only_handoff_action(tmp_path: Path) -> None:
    _app()
    (tmp_path / "Nintendo 3DS").mkdir()
    (tmp_path / "_nds" / "TWiLightMenu").mkdir(parents=True)
    report = inspect_ds_runtime(tmp_path)
    actions = plan_ds_repairs(report)
    panel = DsRuntimeHealthPanel(brand_for_platform("ds").accent)

    panel.set_report(report, actions)

    assert "3DS storage layout" in panel.summary.summary.text()
    assert panel.summary.primary_action.isHidden()
    assert panel.summary.secondary_action.text() == "Use 3DS readiness"


def test_ds_health_panel_unavailable_state_clears_component_rows(tmp_path: Path) -> None:
    _app()
    _twilight_fixture(tmp_path)
    panel = DsRuntimeHealthPanel(brand_for_platform("ds").accent)
    report = inspect_ds_runtime(tmp_path)
    panel.set_report(report, plan_ds_repairs(report))
    assert panel._rows

    panel.set_unavailable("Select removable storage first.")

    assert panel.summary.badge.label.text() == "Unknown"
    assert panel.summary.summary.text() == "Select removable storage first."
    assert not panel._rows
    assert panel.components.isHidden()
