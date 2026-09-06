from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from romm_vita_manager.workspace_dashboard import WorkspaceDashboardWindow


class _Label:
    def __init__(self) -> None:
        self.value = ""

    def setText(self, value: str) -> None:
        self.value = value


class _Panel:
    def __init__(self) -> None:
        self.report = None
        self.actions = None
        self.unavailable = ""
        self.error = ""

    def set_report(self, report, actions) -> None:
        self.report = report
        self.actions = actions

    def set_unavailable(self, summary: str) -> None:
        self.unavailable = summary

    def set_error(self, summary: str) -> None:
        self.error = summary


def _twilight_fixture(root: Path) -> None:
    (root / "_nds" / "TWiLightMenu").mkdir(parents=True)
    (root / "_nds" / "nds-bootstrap-release.nds").write_bytes(b"nds")
    (root / "_nds" / "nds-bootstrap-release.ver").write_text(
        "nds-bootstrap v2.16.0\n", encoding="utf-8"
    )
    (root / "BOOT.NDS").write_bytes(b"boot")


def test_workspace_refresh_ds_health_uses_runtime_service(tmp_path: Path) -> None:
    _twilight_fixture(tmp_path)
    panel = _Panel()
    fake = SimpleNamespace(
        ds_health_panel=panel,
        config={"ds_sd_root": str(tmp_path)},
        ds_validation=_Label(),
    )

    WorkspaceDashboardWindow._refresh_ds_health(fake)

    assert panel.report is not None
    assert panel.report.profile.key == "generic-removable"
    assert fake.ds_validation.value == "Generic removable DS storage"
    assert any(action.key == "create-content-directories" for action in panel.actions)


def test_workspace_refresh_ds_health_handles_missing_storage_without_legacy_validator() -> None:
    panel = _Panel()
    fake = SimpleNamespace(
        ds_health_panel=panel,
        config={},
        ds_validation=_Label(),
    )

    WorkspaceDashboardWindow._refresh_ds_health(fake)

    assert fake.ds_validation.value == "Not configured"
    assert "removable storage" in panel.unavailable


def test_workspace_ds_health_source_keeps_only_directory_creation_automatic() -> None:
    import inspect
    import romm_vita_manager.workspace_dashboard as dashboard

    source = inspect.getsource(dashboard.WorkspaceDashboardWindow._handle_ds_health_action)

    assert "create-content-directories" in source
    assert "create_ds_content_directories" in source
    assert "action.scope == \"safe\"" in source
    assert "QMessageBox.information(self, action.label, action.description)" in source
