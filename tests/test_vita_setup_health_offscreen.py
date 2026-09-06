from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from romm_vita_manager import vita_setup as vita_setup_module
from romm_vita_manager.vita_setup import VitaSetupDialog


_APP: QApplication | None = None


def _app() -> QApplication:
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
    return _APP


def _valid_vita_mount(root: Path) -> None:
    (root / "app" / "VITASHELL").mkdir(parents=True)
    (root / "VitaShell").mkdir()
    (root / "data").mkdir(exist_ok=True)


def _labels(dialog: VitaSetupDialog) -> list[str]:
    return [label.text() for label in dialog.findChildren(QLabel)]


def test_staged_vpk_is_rendered_as_partial_not_installed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    vita = tmp_path / "ux0"
    _valid_vita_mount(vita)
    (vita / "RetroArch.vpk").write_bytes(b"staged-package")
    monkeypatch.setattr(vita_setup_module, "load_config", lambda: {"devices": {}})

    dialog = VitaSetupDialog(vita)
    dialog.show()
    app.processEvents()

    labels = _labels(dialog)
    assert any(
        text.startswith("Partial · Preferred route for supported RetroAchievements systems")
        for text in labels
    )
    assert not any(text.startswith("Installed ·") for text in labels)
    assert not any(
        text.startswith("Present · launch not verified · Preferred route")
        for text in labels
    )

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_dsvita_app_on_ux0_keeps_ur0_dependencies_not_checked(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    vita = tmp_path / "ux0"
    _valid_vita_mount(vita)
    (vita / "app" / "DSVITA000").mkdir(parents=True)
    (vita / "app" / "DSVITA000" / "eboot.bin").write_bytes(b"dsvita")
    monkeypatch.setattr(vita_setup_module, "load_config", lambda: {"devices": {}})

    dialog = VitaSetupDialog(vita)
    dialog.show()
    app.processEvents()

    labels = _labels(dialog)
    assert any(
        text.startswith("Present · launch not verified · Native DS emulator")
        for text in labels
    )
    assert any(text.startswith("Not checked · Runtime shader compiler") for text in labels)
    assert any(text.startswith("Not checked · Kernel bridge") for text in labels)

    dialog.close()
    dialog.deleteLater()
    app.processEvents()
