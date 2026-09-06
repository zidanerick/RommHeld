from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame

from romm_vita_manager import vita_setup as vita_setup_module
from romm_vita_manager.emulators import EMULATORS
from romm_vita_manager.vita_setup import VitaSetupDialog


_APP: QApplication | None = None


def _app() -> QApplication:
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
    return _APP


def test_vita_setup_scrolls_instead_of_compressing_runtime_rows(monkeypatch) -> None:
    app = _app()
    monkeypatch.setattr(vita_setup_module, "load_config", lambda: {"devices": {}})

    dialog = VitaSetupDialog(None)
    dialog.resize(900, 650)
    dialog.show()
    app.processEvents()

    rows = [
        frame
        for frame in dialog.findChildren(QFrame)
        if frame.objectName() == "vitaPackageRow"
    ]

    # Package/runtime rows plus VitaShell, RetroArch-core, libshacccg and kubridge
    # evidence rows all share the compact row contract.
    assert len(rows) == len(EMULATORS) + 4
    assert dialog.setup_scroll.verticalScrollBar().maximum() > 0
    assert all(row.height() >= 40 for row in rows)
    assert dialog.transport_combo.height() >= dialog.transport_combo.sizeHint().height()
    assert dialog.done_button.isVisible()

    dialog.close()
    dialog.deleteLater()
    app.processEvents()
