from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from .emulators import EMULATORS, detect_emulators
from .package_manager import PACKAGES, download_package, package_path, stage_package
from .vita import free_space, total_space


class PackageWorker(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(str, str)
    failed = Signal(str)

    def __init__(self, package_key: str, action: str, vita: Path | None):
        super().__init__()
        self.package_key = package_key
        self.action = action
        self.vita = vita
        self.cancel_event = threading.Event()

    def run(self):
        try:
            package = PACKAGES[self.package_key]
            if self.action == "download":
                def report(done: int, total: int):
                    percent = int(done * 100 / total) if total else 0
                    self.progress.emit(percent, f"Downloading {package.name}: {done / 1024**2:.1f} MiB")

                path = download_package(package, progress=report)
                self.finished_ok.emit("download", str(path))
                return
            if self.vita is None:
                raise RuntimeError("No Vita is connected.")
            target = stage_package(package, self.vita)
            self.finished_ok.emit("stage", str(target))
        except Exception as exc:
            self.failed.emit(str(exc))


class VitaSetupDialog(QDialog):
    def __init__(self, vita: Path | None, parent=None):
        super().__init__(parent)
        self.vita = vita
        self.worker: PackageWorker | None = None
        self.setWindowTitle("Vita Setup")
        self.resize(980, 700)

        layout = QVBoxLayout(self)
        title = QLabel("Vita software, emulator setup, and RetroAchievements readiness")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        if vita is None:
            message = QLabel(
                "No Vita filesystem is currently mounted. Connect VitaShell in USB mode, "
                "then reopen this screen."
            )
            message.setWordWrap(True)
            layout.addWidget(message)
            close = QPushButton("Close")
            close.clicked.connect(self.accept)
            layout.addWidget(close)
            return

        try:
            free = free_space(vita)
            total = total_space(vita)
            layout.addWidget(QLabel(f"Storage: {free / 1024**3:.1f} GiB free of {total / 1024**3:.1f} GiB"))
        except OSError:
            pass

        installed = detect_emulators(vita)
        grid_box = QGroupBox("Detected components")
        grid = QGridLayout(grid_box)
        headers = ("Component", "Status", "Role", "Action")
        for column, text in enumerate(headers):
            grid.addWidget(QLabel(f"<b>{text}</b>"), 0, column)

        self.action_buttons: list[QPushButton] = []
        row = 1
        for emulator in EMULATORS:
            grid.addWidget(QLabel(emulator.name), row, 0)
            status = "✓ Installed" if installed.get(emulator.key) else "? Not detected"
            grid.addWidget(QLabel(status), row, 1)
            grid.addWidget(QLabel(emulator.achievement_role), row, 2)

            package_keys = emulator.package_keys
            if package_keys and not installed.get(emulator.key):
                button = QPushButton("Download / stage")
                button.clicked.connect(lambda checked=False, key=package_keys[0]: self.download_and_stage(key))
            elif package_keys and installed.get(emulator.key):
                button = QPushButton("Package")
                button.clicked.connect(lambda checked=False, key=package_keys[0]: self.download_and_stage(key))
            else:
                button = QPushButton("No package configured")
                button.setEnabled(False)
            self.action_buttons.append(button)
            grid.addWidget(button, row, 3)
            row += 1

        layout.addWidget(grid_box)

        ra = QGroupBox("RetroAchievements")
        ra_layout = QVBoxLayout(ra)
        ra_text = QLabel(
            "RetroFlow is a frontend, not the achievement implementation. For systems supported "
            "by RetroAchievements, RetroArch plus the appropriate libretro core should be treated "
            "as the achievement-first route. N64 is intentionally shown as a separate choice: "
            "DaedalusX64 may be useful for ordinary N64 compatibility, while RetroArch is the route "
            "to evaluate when achievements are the priority."
        )
        ra_text.setWordWrap(True)
        ra_layout.addWidget(ra_text)
        layout.addWidget(ra)

        progress = QGroupBox("Setup activity")
        progress_layout = QVBoxLayout(progress)
        self.activity = QLabel("Ready.")
        self.activity.setTextInteractionFlags(Qt.TextSelectableByMouse)
        progress_layout.addWidget(self.activity)
        layout.addWidget(progress)

        note = QLabel(
            "Downloads are staged first and never silently installed. VPK installation still uses "
            "VitaShell. RetroArch's data archive also requires extraction into ux0:/data/retroarch/."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        close = QPushButton("Close")
        close.clicked.connect(self.reject if self.worker else self.accept)
        layout.addWidget(close)

    def download_and_stage(self, package_key: str) -> None:
        package = PACKAGES[package_key]
        if self.worker and self.worker.isRunning():
            return

        download_needed = not package_path(package).is_file()
        action = "download" if download_needed else "stage"
        if action == "stage" and not self.vita:
            QMessageBox.warning(self, "Vita not connected", "Connect the Vita in VitaShell USB mode first.")
            return

        self.activity.setText(f"Preparing {package.name}…")
        self._set_actions_enabled(False)
        self.worker = PackageWorker(package_key, action, self.vita)
        self.worker.progress.connect(lambda value, text: self.activity.setText(f"{value}% • {text}"))
        self.worker.finished_ok.connect(self._package_finished)
        self.worker.failed.connect(self._package_failed)
        self.worker.start()

    def _set_actions_enabled(self, enabled: bool) -> None:
        for button in self.action_buttons:
            button.setEnabled(enabled)

    def _package_finished(self, action: str, path: str) -> None:
        self._set_actions_enabled(True)
        self.activity.setText(f"Ready: {path}")
        package = PACKAGES[self.worker.package_key] if self.worker else None
        if action == "download" and package is not None and self.vita is not None:
            reply = QMessageBox.question(
                self,
                "Download complete",
                f"{package.name} was downloaded successfully. Stage it to the Vita now?",
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.download_and_stage(package.key)
        elif action == "stage":
            QMessageBox.information(
                self,
                "Package staged",
                f"Copied to:\n{path}\n\nInstall any VPK with VitaShell. Data archives must be extracted according to the package instructions.",
            )

    def _package_failed(self, message: str) -> None:
        self._set_actions_enabled(True)
        self.activity.setText("Setup action failed.")
        QMessageBox.critical(self, "Vita setup failed", message)
