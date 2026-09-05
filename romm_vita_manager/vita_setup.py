from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from .archive_utils import ArchiveEntry
from .design_tokens import DARK, brand_for_platform
from .emulators import EMULATORS, detect_emulators
from .package_manager import PACKAGES, download_package, inspect_package, package_path, stage_package
from .ui_components import AccentButton, SectionHeader, StatusPill, SurfaceCard
from .vita import free_space, total_space


PLAYSTATION_BLUE = brand_for_platform("vita").accent


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
                    self.progress.emit(
                        percent,
                        f"Downloading {package.name}: {done / 1024**2:.1f} MiB",
                    )

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
    """Vita setup workflow with explicit device, package and achievement states."""

    def __init__(self, vita: Path | None, parent=None):
        super().__init__(parent)
        self.vita = vita
        self.worker: PackageWorker | None = None
        self.action_buttons: list[QPushButton] = []

        self.setWindowTitle("PlayStation Vita Setup")
        self.resize(1040, 780)
        self.setMinimumSize(860, 650)

        installed = detect_emulators(vita) if vita is not None else {}
        free_text = "Unavailable"
        storage_detail = "Storage cannot be read until VitaShell exposes the ux0 filesystem over USB."
        if vita is not None:
            try:
                free = free_space(vita)
                total = total_space(vita)
                free_text = f"{free / 1024**3:.1f} GiB free"
                storage_detail = f"{free / 1024**3:.1f} GiB free of {total / 1024**3:.1f} GiB"
            except OSError:
                free_text = "Mounted"
                storage_detail = "The Vita filesystem is mounted, but storage capacity could not be read."

        header = SectionHeader(
            "Prepare your PlayStation Vita",
            "Confirm the mounted Vita first, then prepare only the runtime packages you actually need. RetroAchievements remains an explicit RetroArch/libretro choice rather than a frontend setting.",
        )

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self.device_status = StatusPill(
            "Vita", "Connected" if vita is not None else "Not mounted"
        )
        self.storage_status = StatusPill("Storage", free_text)
        self.ra_status = StatusPill("Achievements", "RetroArch route")
        status_row.addWidget(self.device_status)
        status_row.addWidget(self.storage_status)
        status_row.addWidget(self.ra_status)
        status_row.addStretch(1)

        device_card = SurfaceCard()
        device_card.content.addWidget(self._card_title("1 · Check the Vita connection"))
        if vita is None:
            device_card.content.addWidget(
                self._secondary(
                    "No Vita filesystem is mounted. On the Vita, open VitaShell and press START. Set SELECT button to USB, choose the USB device that contains ux0 (for example the memory card or SD2Vita), close Settings, press SELECT, then connect a USB data cable. Refresh or reopen RommHeld after the filesystem appears. Downloads can still be prepared in the local cache now."
                )
            )
            device_path = QLabel("No mounted Vita path")
        else:
            device_card.content.addWidget(
                self._secondary(
                    "RommHeld is using the mounted ux0 filesystem exposed by VitaShell USB. Keep VitaShell's USB session active while staging files. VPK installation still happens explicitly in VitaShell."
                )
            )
            device_path = QLabel(str(vita))
        device_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        device_path.setStyleSheet(
            f"color:{DARK.text_primary};font-weight:600;background:transparent;"
        )
        device_card.content.addWidget(device_path)
        device_card.content.addWidget(self._secondary(storage_detail))

        software_card = SurfaceCard()
        software_card.content.addWidget(self._card_title("2 · Prepare runtime software"))
        software_card.content.addWidget(
            self._secondary(
                "Detected software is shown as device evidence. Package actions verify SHA-256 when the upstream source provides a digest; staging is separate, and archive packages are never extracted blindly."
            )
        )

        for emulator in EMULATORS:
            row = QFrame()
            row.setObjectName("vitaPackageRow")
            row.setStyleSheet(
                f"QFrame#vitaPackageRow{{background:{DARK.surface_raised};"
                f"border:1px solid {DARK.separator};border-radius:10px;}}"
            )
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 9, 10, 9)
            row_layout.setSpacing(12)

            text = QVBoxLayout()
            text.setContentsMargins(0, 0, 0, 0)
            text.setSpacing(2)
            name = QLabel(emulator.name)
            name.setStyleSheet(
                f"color:{DARK.text_primary};font-weight:700;background:transparent;"
            )
            state = "Installed" if installed.get(emulator.key) else "Not detected"
            detail = QLabel(f"{state} · {emulator.achievement_role}")
            detail.setWordWrap(True)
            detail.setStyleSheet(
                f"color:{DARK.text_secondary};font-size:11px;background:transparent;"
            )
            text.addWidget(name)
            text.addWidget(detail)
            row_layout.addLayout(text, 1)

            package_keys = emulator.package_keys
            if not package_keys:
                button = QPushButton("No package configured")
                button.setEnabled(False)
            elif installed.get(emulator.key):
                button = QPushButton("Inspect package")
                button.clicked.connect(
                    lambda checked=False, key=package_keys[0]: self.prepare_package(key)
                )
            else:
                label = "Download / stage" if vita is not None else "Download package"
                button = AccentButton(label, PLAYSTATION_BLUE)
                button.clicked.connect(
                    lambda checked=False, key=package_keys[0]: self.prepare_package(key)
                )
            self.action_buttons.append(button)
            row_layout.addWidget(button)
            software_card.content.addWidget(row)

        achievements_card = SurfaceCard()
        achievements_card.content.addWidget(
            self._card_title("3 · Choose the achievement-capable route intentionally")
        )
        achievements_card.content.addWidget(
            self._secondary(
                "RetroFlow is a frontend, not the achievement implementation. For supported systems, RetroArch plus the appropriate libretro core remains the achievement-first route. Emu4Vita++ is a separate RetroFlow-supported emulator path and should not silently replace RetroArch when achievements are the priority."
            )
        )

        activity_card = SurfaceCard()
        activity_card.content.addWidget(self._card_title("Setup activity"))
        self.activity = QLabel("Ready.")
        self.activity.setWordWrap(True)
        self.activity.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        activity_card.content.addWidget(self.activity)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        activity_card.content.addWidget(self.progress_bar)
        activity_card.content.addWidget(
            self._secondary(
                "VPKs are staged for VitaShell installation. Archive packages are inspected before extraction, and RommHeld does not assume that a ZIP belongs in ux0:/data/."
            )
        )

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close = QPushButton("Done")
        close.clicked.connect(self.accept)
        close_row.addWidget(close)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(header)
        layout.addLayout(status_row)
        layout.addWidget(device_card)
        layout.addWidget(software_card, 1)
        layout.addWidget(achievements_card)
        layout.addWidget(activity_card)
        layout.addLayout(close_row)

    def _card_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"color:{DARK.text_primary};font-size:15px;font-weight:700;background:transparent;"
        )
        return label

    def _secondary(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{DARK.text_secondary};background:transparent;")
        return label

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
            QMessageBox.warning(
                self,
                "Vita not connected",
                "Open VitaShell, press START, set SELECT button to USB, close Settings, press SELECT, then connect the Vita with a USB data cable before staging files.",
            )
            return
        self.activity.setText(f"Preparing {package.name}…")
        self._set_actions_enabled(False)
        self.progress_bar.setVisible(True)
        if action == "download":
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
        else:
            self.progress_bar.setRange(0, 0)
        self.worker = PackageWorker(package_key, action, self.vita)
        self.worker.progress.connect(self._package_progress)
        self.worker.finished_ok.connect(self._package_finished)
        self.worker.archive_ready.connect(self._archive_ready)
        self.worker.failed.connect(self._package_failed)
        self.worker.start()

    def _package_progress(self, value: int, text: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(value)
        self.activity.setText(f"{value}% · {text}")

    def _finish_activity(self) -> None:
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

    def _set_actions_enabled(self, enabled: bool) -> None:
        for button in self.action_buttons:
            if button.text() != "No package configured":
                button.setEnabled(enabled)

    def _package_finished(self, action: str, path: str) -> None:
        self._set_actions_enabled(True)
        self._finish_activity()
        self.activity.setText(f"Ready: {path}")
        package = PACKAGES[self.worker.package_key] if self.worker else None
        if action == "download" and package is not None and self.vita is not None:
            reply = QMessageBox.question(
                self,
                "Download complete",
                f"{package.name} was downloaded successfully. Stage it to the Vita now?",
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
        self._finish_activity()
        package = PACKAGES[self.worker.package_key] if self.worker else None
        archive_entries = [item for item in entries if isinstance(item, ArchiveEntry)]
        lines = []
        for item in archive_entries[:80]:
            prefix = "[DIR] " if item.is_directory else "      "
            lines.append(
                f"{prefix}{item.name}"
                + ("" if item.is_directory else f" ({item.size / 1024**2:.1f} MiB)")
            )
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
        self._finish_activity()
        self.activity.setText("Setup action failed.")
        QMessageBox.critical(self, "Vita setup failed", message)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(
                self,
                "Setup action in progress",
                "The current package action must finish before this window can close.",
            )
            event.ignore()
            return
        super().closeEvent(event)
