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

from .archive_utils import ArchiveEntry
from .emulators import EMULATORS, detect_emulators
from .package_manager import PACKAGES, download_package, inspect_package, package_path, stage_package
from .vita import free_space, total_space


class PackageWorker(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(str, str)
    archive_ready = Signal(str, object)
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
                if package.requires_archive_review:
                    entries = inspect_package(package)
                    self.archive_ready.emit(str(path), entries)
                else:
                    self.finished_ok.emit("download", str(path))
                return
            if self.action == "inspect":
                entries = inspect_package(package)
                self.archive_ready.emit(str(package_path(package)), entries)
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
        self.resize(1040, 760)

        layout = QVBoxLayout(self)
        title = QLabel("Vita software, emulator setup, and RetroAchievements readiness")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        if vita is None:
            message = QLabel(
                "No Vita filesystem is currently mounted. Connect VitaShell in USB mode, then reopen this screen."
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
        for column, text in enumerate(("Component", "Status", "RetroAchievements role", "Action")):
            grid.addWidget(QLabel(f"<b>{text}</b>"), 0, column)

        self.action_buttons: list[QPushButton] = []
        row = 1
        for emulator in EMULATORS:
            grid.addWidget(QLabel(emulator.name), row, 0)
            grid.addWidget(QLabel("✓ Installed" if installed.get(emulator.key) else "? Not detected"), row, 1)
            grid.addWidget(QLabel(emulator.achievement_role), row, 2)

            package_keys = emulator.package_keys
            if not package_keys:
                button = QPushButton("No package configured")
                button.setEnabled(False)
            elif installed.get(emulator.key):
                button = QPushButton("Package / inspect")
                button.clicked.connect(lambda checked=False, key=package_keys[0]: self.prepare_package(key))
            else:
                button = QPushButton("Download / stage")
                button.clicked.connect(lambda checked=False, key=package_keys[0]: self.prepare_package(key))
            self.action_buttons.append(button)
            grid.addWidget(button, row, 3)
            row += 1

        layout.addWidget(grid_box)

        ra = QGroupBox("RetroAchievements")
        ra_layout = QVBoxLayout(ra)
        ra_text = QLabel(
            "RetroFlow is a frontend, not the achievement implementation. For supported systems, "
            "RetroArch plus the appropriate libretro core remains the achievement-first route. "
            "Emu4Vita++ is a separate RetroFlow-supported emulator path, so it should not silently "
            "replace RetroArch when achievement support is the priority."
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
            "VPKs are staged for VitaShell installation. Archive packages are inspected before extraction; "
            "the manager never assumes that a ZIP belongs in ux0:/data/."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

    def prepare_package(self, package_key: str) -> None:
        package = PACKAGES[package_key]
        if self.worker and self.worker.isRunning():
            return
        if package.requires_archive_review and package_path(package).is_file():
            self._start_worker(package_key, "inspect")
            return
        self._start_worker(package_key, "download")

    def _start_worker(self, package_key: str, action: str) -> None:
        package = PACKAGES[package_key]
        if action == "stage" and not self.vita:
            QMessageBox.warning(self, "Vita not connected", "Connect the Vita in VitaShell USB mode first.")
            return
        self.activity.setText(f"Preparing {package.name}…")
        self._set_actions_enabled(False)
        self.worker = PackageWorker(package_key, action, self.vita)
        self.worker.progress.connect(lambda value, text: self.activity.setText(f"{value}% • {text}"))
        self.worker.finished_ok.connect(self._package_finished)
        self.worker.archive_ready.connect(self._archive_ready)
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
                f"{package.name} was downloaded and verified. Stage it to the Vita now?",
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._start_worker(package.key, "stage")
        elif action == "stage":
            QMessageBox.information(
                self,
                "Package staged",
                f"Copied to:\n{path}\n\nInstall VPK packages with VitaShell.",
            )

    def _archive_ready(self, path: str, entries: object) -> None:
        self._set_actions_enabled(True)
        package = PACKAGES[self.worker.package_key] if self.worker else None
        archive_entries = [item for item in entries if isinstance(item, ArchiveEntry)]
        lines = []
        for item in archive_entries[:80]:
            prefix = "[DIR] " if item.is_directory else "      "
            lines.append(f"{prefix}{item.name}" + ("" if item.is_directory else f" ({item.size / 1024**2:.1f} MiB)"))
        extra = len(archive_entries) - len(lines)
        if extra > 0:
            lines.append(f"… {extra} more entries")
        body = (
            f"Archive cached at:\n{path}\n\n"
            "Nothing has been extracted to the Vita. Review these members before choosing a destination:\n\n"
            + "\n".join(lines)
        )
        self.activity.setText(f"Inspected archive: {len(archive_entries)} entries")
        QMessageBox.information(self, "Archive contents", body)
        self._maybe_stage_archive(package)

    def _maybe_stage_archive(self, package) -> None:
        if package is None or self.vita is None:
            return
        reply = QMessageBox.information(
            self,
            "Archive requires review",
            f"{package.name} is an archive and its Vita extraction layout has not been verified by the manager.\n\n"
            "It will not be extracted automatically. Leave it in the Linux cache until an explicit package rule is added.",
        )
        _ = reply

    def _package_failed(self, message: str) -> None:
        self._set_actions_enabled(True)
        self.activity.setText("Setup action failed.")
        QMessageBox.critical(self, "Vita setup failed", message)
