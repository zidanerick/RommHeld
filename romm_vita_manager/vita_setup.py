from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
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
from .config import load_config
from .design_tokens import DARK, brand_for_platform
from .emulators import EMULATORS, detect_emulators
from .package_manager import PACKAGES, download_package, inspect_package, package_path, stage_package
from .ui_components import AccentButton, SectionHeader, StatusPill, SurfaceCard
from .vita import free_space, is_vita_mount, total_space
from .vita_ftp import VitaFtpSettings
from .vita_package_transport import stage_package_via_ftp


PLAYSTATION_BLUE = brand_for_platform("vita").accent


class PackageWorker(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(str, str)
    archive_ready = Signal(str, object)
    cancelled = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        package_key: str,
        action: str,
        vita: Path | None,
        *,
        transport: str = "usb",
        ftp_settings: VitaFtpSettings | None = None,
    ):
        super().__init__()
        self.package_key = package_key
        self.action = action
        self.vita = vita
        self.transport = transport
        self.ftp_settings = ftp_settings
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

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

                path = download_package(
                    package,
                    progress=report,
                    cancel_event=self.cancel_event,
                )
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
            if self.transport == "ftp":
                if self.ftp_settings is None:
                    raise RuntimeError("VitaShell FTP is not configured.")
                source = package_path(package)
                total = source.stat().st_size if source.is_file() else 0

                def report_ftp(done: int):
                    percent = int(done * 100 / total) if total else 0
                    self.progress.emit(
                        percent,
                        f"Staging {package.name} over VitaShell FTP: {done / 1024**2:.1f} MiB",
                    )

                result, target = stage_package_via_ftp(
                    package,
                    self.ftp_settings,
                    cancel_event=self.cancel_event,
                    progress=report_ftp,
                )
                if result == "cancelled":
                    raise InterruptedError(f"Staging {package.name} was cancelled.")
                self.finished_ok.emit("stage", target)
                return
            if self.vita is None or not is_vita_mount(self.vita):
                raise RuntimeError(
                    "The VitaShell USB mount is no longer available. Reconnect the Vita or choose VitaShell FTP."
                )
            target = stage_package(
                package,
                self.vita,
                cancel_event=self.cancel_event,
            )
            self.finished_ok.emit("stage", str(target))
        except InterruptedError as exc:
            self.cancelled.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))


class VitaSetupDialog(QDialog):
    """Vita setup workflow with explicit device, package and achievement states."""

    def __init__(self, vita: Path | None, parent=None):
        super().__init__(parent)
        self.vita = vita if vita is not None and is_vita_mount(vita) else None
        vita = self.vita
        self.worker: PackageWorker | None = None
        self.action_buttons: list[QPushButton] = []
        self._pending_stage_key: str | None = None
        saved_ftp = load_config().get("devices", {}).get("vita_ftp", {})
        self._ftp_host = str(saved_ftp.get("host", "")).strip()
        try:
            self._ftp_port = int(saved_ftp.get("port", 1337))
            if not 1 <= self._ftp_port <= 65535:
                raise ValueError
        except (TypeError, ValueError):
            self._ftp_port = 1337

        self.setWindowTitle("PlayStation Vita Setup")
        self.resize(1040, 780)
        self.setMinimumSize(860, 650)

        installed = detect_emulators(vita) if vita is not None else {}
        free_text = "Unavailable"
        storage_detail = "Storage capacity is available only while VitaShell exposes ux0 over USB."
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
            "Choose the VitaShell transport, then prepare only the runtime packages you actually need. USB remains recommended on handheld Vita; FTP also supports wireless staging and PlayStation TV.",
        )

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        device_state = (
            "USB mounted"
            if vita is not None
            else "FTP configured"
            if self._ftp_host
            else "Not connected"
        )
        self.device_status = StatusPill("Vita", device_state)
        self.storage_status = StatusPill("Storage", free_text)
        self.ra_status = StatusPill("Achievements", "RetroArch route")
        status_row.addWidget(self.device_status)
        status_row.addWidget(self.storage_status)
        status_row.addWidget(self.ra_status)
        status_row.addStretch(1)

        device_card = SurfaceCard()
        device_card.content.addWidget(self._card_title("1 · Choose the VitaShell transport"))
        device_card.content.addWidget(
            self._secondary(
                "USB is faster and exposes storage capacity, so it remains the recommended handheld path. FTP is useful for wireless transfers and PlayStation TV. FTP must already be configured from Device → Send file / configure FTP."
            )
        )
        self.transport_combo = QComboBox()
        self.transport_combo.addItem("VitaShell USB · Recommended", "usb")
        self.transport_combo.addItem("VitaShell FTP · Wireless / PlayStation TV", "ftp")
        if vita is None and self._ftp_host:
            self.transport_combo.setCurrentIndex(1)
        self.transport_combo.currentIndexChanged.connect(self._transport_changed)
        device_card.content.addWidget(self.transport_combo)

        if vita is None:
            usb_detail = (
                "USB: not mounted. In VitaShell press START, set SELECT button to USB, choose the USB device that contains ux0, close Settings, press SELECT, then connect a USB data cable."
            )
        else:
            usb_detail = f"USB: {vita}"
        ftp_detail = (
            f"FTP: {self._ftp_host}:{self._ftp_port}"
            if self._ftp_host
            else "FTP: not configured. Use Device → Send file / configure FTP."
        )
        device_path = QLabel(f"{usb_detail}\n{ftp_detail}")
        device_path.setWordWrap(True)
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
                "Detected software is USB-side evidence only. Package actions verify SHA-256 when the upstream source provides a digest; staging is separate, and archive packages are never extracted blindly."
            )
        )

        stage_available = vita is not None or bool(self._ftp_host)
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
            state = (
                "Not checked"
                if vita is None
                else "Detected"
                if installed.get(emulator.key)
                else "Not detected"
            )
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
                label = "Download / stage" if stage_available else "Download package"
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
        self.cancel_button = QPushButton("Cancel current action")
        self.cancel_button.setVisible(False)
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_worker)
        activity_card.content.addWidget(self.cancel_button)
        activity_card.content.addWidget(
            self._secondary(
                "VPKs are staged for VitaShell installation. FTP staging uses the same verified temporary-upload and safe-replacement transport as other Vita FTP transfers. Archive packages are inspected before extraction."
            )
        )

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        self.done_button = QPushButton("Done")
        self.done_button.clicked.connect(self.accept)
        close_row.addWidget(self.done_button)

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

        self._transport_changed()

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

    def _selected_transport(self) -> str:
        return str(self.transport_combo.currentData() or "usb")

    def _ftp_settings(self) -> VitaFtpSettings | None:
        if not self._ftp_host:
            return None
        return VitaFtpSettings(host=self._ftp_host, port=self._ftp_port)

    def _can_stage(self) -> bool:
        if self._selected_transport() == "ftp":
            return self._ftp_settings() is not None
        return self.vita is not None and is_vita_mount(self.vita)

    def _transport_changed(self, _index: int | None = None) -> None:
        if self._selected_transport() == "ftp":
            if self._ftp_host:
                self.device_status.set_value("FTP configured")
                self.storage_status.set_value("Checked during transfer")
                self.activity.setText(
                    "FTP selected. Start VitaShell FTP with SELECT before staging a package."
                )
            else:
                self.device_status.set_value("FTP setup required")
                self.storage_status.set_value("Unavailable")
                self.activity.setText(
                    "Configure VitaShell FTP from Device → Send file / configure FTP before staging."
                )
        else:
            usb_available = self.vita is not None and is_vita_mount(self.vita)
            if not usb_available:
                self.vita = None
            self.device_status.set_value("USB mounted" if usb_available else "Not mounted")
            if not usb_available:
                self.storage_status.set_value("Unavailable")
                self.activity.setText("USB selected. Mount ux0 through VitaShell before staging.")
            else:
                try:
                    self.storage_status.set_value(f"{free_space(self.vita) / 1024**3:.1f} GiB free")
                except OSError:
                    self.storage_status.set_value("Mounted")
                self.activity.setText("USB selected. Ready to prepare runtime packages.")

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
        transport = self._selected_transport()
        ftp_settings = self._ftp_settings()
        if action == "stage" and not self._can_stage():
            if transport == "ftp":
                message = (
                    "VitaShell FTP is not configured. Open Device → Send file / configure FTP, "
                    "enter the IP address and port shown by VitaShell, then retry."
                )
            else:
                message = (
                    "Open VitaShell, press START, set SELECT button to USB, close Settings, "
                    "press SELECT, then connect the Vita with a USB data cable before staging files."
                )
            QMessageBox.warning(self, "Vita transport unavailable", message)
            return
        self.activity.setText(f"Preparing {package.name}…")
        self._set_actions_enabled(False)
        self.transport_combo.setEnabled(False)
        self.done_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        cancellable = action in {"download", "stage"}
        self.cancel_button.setVisible(cancellable)
        self.cancel_button.setEnabled(cancellable)
        if cancellable:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
        else:
            self.progress_bar.setRange(0, 0)
        self.worker = PackageWorker(
            package_key,
            action,
            self.vita,
            transport=transport,
            ftp_settings=ftp_settings,
        )
        self.worker.progress.connect(self._package_progress)
        self.worker.finished_ok.connect(self._package_finished)
        self.worker.archive_ready.connect(self._archive_ready)
        self.worker.cancelled.connect(self._package_cancelled)
        self.worker.failed.connect(self._package_failed)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _cancel_worker(self) -> None:
        if self.worker is None or not self.worker.isRunning():
            return
        self.worker.cancel()
        self.cancel_button.setEnabled(False)
        package = PACKAGES[self.worker.package_key]
        self.activity.setText(f"Cancelling {package.name}…")

    def _package_progress(self, value: int, text: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(value)
        self.activity.setText(f"{value}% · {text}")

    def _finish_activity(self) -> None:
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.cancel_button.setVisible(False)
        self.cancel_button.setEnabled(False)

    def _set_actions_enabled(self, enabled: bool) -> None:
        for button in self.action_buttons:
            if button.text() != "No package configured":
                button.setEnabled(enabled)

    def _worker_finished(self) -> None:
        pending_stage = self._pending_stage_key
        self._pending_stage_key = None
        self.worker = None
        self.transport_combo.setEnabled(True)
        self.done_button.setEnabled(True)
        self._set_actions_enabled(True)

        if pending_stage is None or not self._can_stage():
            return
        package = PACKAGES[pending_stage]
        transport_label = (
            "VitaShell FTP" if self._selected_transport() == "ftp" else "VitaShell USB"
        )
        reply = QMessageBox.question(
            self,
            "Download complete",
            f"{package.name} was downloaded successfully. Stage it using {transport_label} now?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_worker(package.key, "stage")

    def _package_finished(self, action: str, path: str) -> None:
        self._finish_activity()
        self.activity.setText(f"Ready: {path}")
        package = PACKAGES[self.worker.package_key] if self.worker else None
        if action == "download" and package is not None and self._can_stage():
            self._pending_stage_key = package.key
        elif action == "stage":
            QMessageBox.information(
                self,
                "Package staged",
                f"Staged to:\n{path}\n\nInstall VPK packages with VitaShell.",
            )

    def _archive_ready(self, path: str, entries: object) -> None:
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
        if package is None:
            return
        reply = QMessageBox.information(
            self,
            "Archive requires review",
            f"{package.name} is an archive and its Vita extraction layout has not been verified by the manager.\n\n"
            "It will not be extracted automatically. Leave it in the local cache until an explicit package rule is added."
        )
        _ = reply

    def _package_cancelled(self, message: str) -> None:
        self._pending_stage_key = None
        self._finish_activity()
        self.activity.setText(message or "Setup action cancelled.")

    def _package_failed(self, message: str) -> None:
        self._finish_activity()
        self.activity.setText("Setup action failed.")
        QMessageBox.critical(self, "Vita setup failed", message)

    def _worker_active(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def _show_setup_action_in_progress(self) -> None:
        QMessageBox.information(
            self,
            "Setup action in progress",
            "Cancel the current package action or allow it to finish before closing this window.",
        )

    def accept(self) -> None:
        if self._worker_active():
            self._show_setup_action_in_progress()
            return
        super().accept()

    def reject(self) -> None:
        if self._worker_active():
            self._show_setup_action_in_progress()
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker_active():
            self._show_setup_action_in_progress()
            event.ignore()
            return
        super().closeEvent(event)
