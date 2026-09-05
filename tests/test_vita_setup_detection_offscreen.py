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


def _labels(dialog: VitaSetupDialog) -> list[str]:
    return [label.text() for label in dialog.findChildren(QLabel)]


def test_vita_setup_labels_usb_filesystem_evidence_as_detected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    vita = tmp_path / "ux0"
    (vita / "app" / "VITASHELL").mkdir(parents=True)
    (vita / "VitaShell").mkdir()
    (vita / "data" / "retroarch").mkdir(parents=True)
    (vita / "app" / "RETROARCH").mkdir(parents=True)

    monkeypatch.setattr(vita_setup_module, "load_config", lambda: {"devices": {}})

    dialog = VitaSetupDialog(vita)
    dialog.show()
    app.processEvents()

    labels = _labels(dialog)

    assert any(
        text.startswith("Detected · Preferred route for supported RetroAchievements systems")
        for text in labels
    )
    assert any(
        text.startswith("Detected · Required companion data for RetroArch")
        for text in labels
    )
    assert not any(text.startswith("Installed ·") for text in labels)

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_vita_setup_marks_runtime_state_not_checked_without_usb_inspection(
    monkeypatch,
) -> None:
    app = _app()
    monkeypatch.setattr(
        vita_setup_module,
        "load_config",
        lambda: {
            "devices": {
                "vita_ftp": {
                    "host": "192.0.2.10",
                    "port": 1337,
                }
            }
        },
    )

    dialog = VitaSetupDialog(None)
    dialog.show()
    app.processEvents()

    labels = _labels(dialog)

    assert dialog.transport_combo.currentData() == "ftp"
    assert any(
        text.startswith("Not checked · Preferred route for supported RetroAchievements systems")
        for text in labels
    )
    assert any(
        text.startswith("Not checked · Required companion data for RetroArch")
        for text in labels
    )
    assert not any(text.startswith("Detected ·") for text in labels)
    assert not any(text.startswith("Not detected ·") for text in labels)

    dialog.close()
    dialog.deleteLater()
    app.processEvents()
