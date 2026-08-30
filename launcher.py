#!/usr/bin/env python3
"""Compatibility launcher that adds the modular Vita Setup screen."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEGACY = ROOT / "romm_vita_manager.py"

spec = importlib.util.spec_from_file_location("romm_vita_manager_legacy", LEGACY)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {LEGACY}")
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)

from PySide6.QtWidgets import QApplication, QPushButton, QHBoxLayout  # noqa: E402

from romm_vita_manager.vita_setup import VitaSetupDialog  # noqa: E402
from romm_vita_manager.vita import find_vita_mounts  # noqa: E402


class ManagedMainWindow(legacy.MainWindow):
    def __init__(self, config: dict):
        super().__init__(config)

        self.vita_setup_button = QPushButton("Vita Setup")
        self.vita_setup_button.clicked.connect(self.open_vita_setup)

        # Add beside the existing Settings control without touching the prototype UI code.
        top = self.centralWidget().layout().itemAt(0).layout()
        top.insertWidget(top.count() - 1, self.vita_setup_button)

    def open_vita_setup(self):
        mounts = find_vita_mounts()
        vita = mounts[0] if mounts else self.vita
        dialog = VitaSetupDialog(vita, self)
        dialog.exec()
        self.detect_vita()
        self.refresh_games()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("RomM Vita Manager")
    app.setApplicationVersion("0.6")

    config = legacy.load_config()
    if not config.get("setup_complete"):
        wizard = legacy.SetupWizard(config)
        if wizard.exec() != legacy.QDialog.DialogCode.Accepted:
            return
        config = legacy.load_config()

    window = ManagedMainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
