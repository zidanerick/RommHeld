from __future__ import annotations

import threading
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from .design_tokens import DARK, brand_for_platform
from .open_agb_config import detect_open_agb_config_format, open_agb_config_path
from .open_agb_settings import OpenAgbSettingsDialog
from .platform_services import is_web_url, open_external_url
from .three_ds_apps import APP_BY_KEY, THREE_DS_APPS, ThreeDSAppStatus, scan_three_ds_apps
from .three_ds_packages import download_package, package_for_app, resolve_package, stage_package
from .three_ds_readiness import ReadinessRequirement, evaluate_readiness
from .three_ds_runtime_details import (
    RETROARCH_CORE_PROFILES,
    scan_retroarch_route,
    scan_twilight_runtime,
)
from .ui_components import AccentButton, SectionHeader, StatusPill, SurfaceCard


NINTENDO_RED = brand_for_platform("3ds").accent


class ThreeDSPackageStageWorker(QThread):
    progress = Signal(int)
    status_changed = Signal(str)
    completed = Signal(str, str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, app_key: str, sd_root: Path):
        super().__init__()
        self.app_key = app_key
        self.sd_root = sd_root
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        package = package_for_app(self.app_key)
        if package is None:
            self.failed.emit("This component is not eligible for direct RommHeld staging.")
            return
        try:
            if self.cancel_event.is_set():
                raise InterruptedError
            self.status_changed.emit(f"Checking the latest {package.name} release…")
            resolved = resolve_package(package)
            if self.cancel_event.is_set():
                raise InterruptedError
            self.status_changed.emit(
                f"Downloading {package.name} {resolved.version} from its upstream GitHub release…"
            )

            def report(completed: int, total: int) -> None:
                if total > 0:
                    self.progress.emit(max(0, min(100, int(completed * 100 / total))))

            downloaded = download_package(
                resolved,
                progress=report,
                cancel_event=self.cancel_event,
            )
            if self.cancel_event.is_set():
                raise InterruptedError
            self.status_changed.emit(f"Verifying and staging {package.name} to the 3DS SD card…")
            target = stage_package(resolved, downloaded, self.sd_root)
            self.completed.emit(package.name, str(target))
        except InterruptedError:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class ThreeDSReadinessDialog(QDialog):
    """Inspect 3DS readiness and manage only narrowly supported runtime actions."""

    def __init__(
        self,
        sd_root: Path,
        *,
        target_keys: Iterable[str] = (),
        needs_ftp: bool = True,
        needs_cia_install: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.sd_root = sd_root.expanduser()
        self.target_keys = tuple(target_keys)
        self.needs_ftp = needs_ftp
        self.needs_cia_install = needs_cia_install
        self.worker: ThreeDSPackageStageWorker | None = None
        self._closing_requested = False
        self._requirements: dict[str, ReadinessRequirement] = {}
        self._statuses: dict[str, ThreeDSAppStatus] = {}

        self.setWindowTitle("Nintendo 3DS Readiness")
        self.resize(860, 700)
        self.setMinimumSize(760, 600)

        header = SectionHeader(
            "Nintendo 3DS readiness",
            "Check the mounted SD card, distinguish required components from optional runtimes, and stage only simple upstream homebrew packages that RommHeld can verify safely.",
        )

        self.readiness_status = StatusPill("Readiness", "Checking…")
        self.sd_label = QLabel(str(self.sd_root))
        self.sd_label.setWordWrap(True)
        self.sd_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.sd_label.setProperty("secondary", True)
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        status_row.addWidget(self.readiness_status)
        status_row.addWidget(self.sd_label, 1)

        inventory_card = SurfaceCard()
        inventory_title = QLabel("Runtime and homebrew inventory")
        inventory_title.setStyleSheet(
            f"color:{DARK.text_primary};font-size:15px;font-weight:700;background:transparent;"
        )
        inventory_note = QLabel(
            "Detected means RommHeld found reliable SD-side evidence. Some CIA-installed applications cannot be proven from SD files alone and are shown as needing on-console confirmation instead of being called missing."
        )
        inventory_note.setWordWrap(True)
        inventory_note.setProperty("secondary", True)
        self.component_list = QListWidget()
        self.component_list.currentItemChanged.connect(self._selection_changed)
        inventory_card.content.addWidget(inventory_title)
        inventory_card.content.addWidget(inventory_note)
        inventory_card.content.addWidget(self.component_list, 1)

        self.detail_title = QLabel("Select a component")
        self.detail_title.setStyleSheet(
            f"color:{DARK.text_primary};font-size:15px;font-weight:700;background:transparent;"
        )
        self.detail_text = QLabel(
            "Select a runtime or utility to see why it matters and which actions RommHeld can perform safely."
        )
        self.detail_text.setWordWrap(True)
        self.detail_text.setProperty("secondary", True)

        self.open_upstream_button = QPushButton("Open upstream")
        self.open_upstream_button.setEnabled(False)
        self.open_upstream_button.clicked.connect(self.open_upstream)
        self.configure_button = QPushButton("Configure")
        self.configure_button.setEnabled(False)
        self.configure_button.clicked.connect(self.configure_selected)
        self.stage_button = AccentButton("Stage to SD", NINTENDO_RED)
        self.stage_button.setEnabled(False)
        self.stage_button.clicked.connect(self.stage_selected)
        detail_actions = QHBoxLayout()
        detail_actions.setSpacing(8)
        detail_actions.addWidget(self.open_upstream_button)
        detail_actions.addWidget(self.configure_button)
        detail_actions.addStretch(1)
        detail_actions.addWidget(self.stage_button)

        detail_card = SurfaceCard()
        detail_card.content.addWidget(self.detail_title)
        detail_card.content.addWidget(self.detail_text)
        detail_card.content.addLayout(detail_actions)

        self.operation_status = QLabel("No package operation is active.")
        self.operation_status.setWordWrap(True)
        self.operation_status.setProperty("secondary", True)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        self.cancel_button = QPushButton("Cancel staging")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_staging)
        operation_row = QHBoxLayout()
        operation_row.addWidget(self.operation_status, 1)
        operation_row.addWidget(self.cancel_button)

        refresh = QPushButton("Refresh checks")
        refresh.clicked.connect(self.refresh)
        close = QPushButton("Done")
        close.clicked.connect(self.close)
        bottom = QHBoxLayout()
        bottom.addWidget(refresh)
        bottom.addStretch(1)
        bottom.addWidget(close)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(header)
        layout.addLayout(status_row)
        layout.addWidget(inventory_card, 1)
        layout.addWidget(detail_card)
        layout.addWidget(self.progress)
        layout.addLayout(operation_row)
        layout.addLayout(bottom)

        self.refresh()

    def _selected_app_key(self) -> str | None:
        item = self.component_list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    def _requirement_label(self, app_key: str) -> str:
        requirement = self._requirements.get(app_key)
        if requirement is None:
            app = APP_BY_KEY[app_key]
            return "Optional runtime" if app.role == "runtime" else "Optional utility"
        return requirement.importance.capitalize()

    def _state_label(self, app_key: str, status: ThreeDSAppStatus) -> str:
        if status.detected:
            return "Detected"
        requirement = self._requirements.get(app_key)
        if (
            requirement is not None
            and requirement.importance == "required"
            and status.definition.installed_title_may_exist_without_sd_marker
        ):
            return "Confirm on console"
        if requirement is not None and requirement.importance == "required":
            return "Missing"
        if status.definition.installed_title_may_exist_without_sd_marker:
            return "Not detected on SD"
        return "Not detected"

    def _runtime_detail(self, app_key: str) -> str:
        if app_key == "twilight":
            return scan_twilight_runtime(self.sd_root).note
        if app_key != "retroarch":
            return ""

        active_files: set[str] = set()
        inactive_files: set[str] = set()
        firmware_notes: list[str] = []
        for slug in RETROARCH_CORE_PROFILES:
            route = scan_retroarch_route(self.sd_root, slug)
            active_files.update(path.name for path in route.active_core_files)
            inactive_files.update(path.name for path in route.inactive_core_files)
            if route.state in {"firmware_unverified", "missing_firmware"}:
                firmware_notes.append(f"{slug}: {route.note}")

        lines: list[str] = []
        if active_files:
            lines.append(
                "SD-visible files in the active core directory: "
                + ", ".join(sorted(active_files, key=str.casefold))
                + ". CIA files are installer evidence, not proof that the core title is installed."
            )
        else:
            lines.append(
                "No audited core package/executable files are visible in the active core directory. CIA-installed cores may still exist on the console."
            )
        if inactive_files:
            lines.append(
                "Matching files in Cores-Notused: "
                + ", ".join(sorted(inactive_files, key=str.casefold))
                + ". These are treated as inactive."
            )
        lines.extend(firmware_notes)
        lines.append(
            "RetroAchievements recommendations are core-specific. Current 3DS SNES cores are not recommended for achievements, and the current official 3DS core bundle does not provide an audited N64 core."
        )
        return "\n".join(lines)

    def refresh(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        report = evaluate_readiness(
            self.sd_root,
            self.target_keys,
            needs_ftp=self.needs_ftp,
            needs_cia_install=self.needs_cia_install,
            include_utilities=True,
        )
        self._requirements = {
            item.requirement.app_key: item.requirement for item in report.items
        }
        self._statuses = scan_three_ds_apps(self.sd_root)

        if report.state == "ready":
            self.readiness_status.set_value("Ready")
        elif report.state == "needs_confirmation":
            self.readiness_status.set_value("Confirm on console")
        else:
            self.readiness_status.set_value("Action required")

        selected_key = self._selected_app_key()
        self.component_list.blockSignals(True)
        self.component_list.clear()
        selected_row = -1
        for index, app in enumerate(THREE_DS_APPS):
            status = self._statuses[app.key]
            importance = self._requirement_label(app.key)
            state = self._state_label(app.key, status)
            item = QListWidgetItem(f"{app.name}  ·  {importance}  ·  {state}")
            item.setData(Qt.ItemDataRole.UserRole, app.key)
            reason = self._requirements.get(app.key)
            item.setToolTip(reason.reason if reason is not None else app.description)
            self.component_list.addItem(item)
            if app.key == selected_key:
                selected_row = index
        self.component_list.blockSignals(False)
        if self.component_list.count():
            self.component_list.setCurrentRow(selected_row if selected_row >= 0 else 0)
        else:
            self._selection_changed(None, None)

    def _selection_changed(self, current, previous) -> None:
        app_key = self._selected_app_key()
        if app_key is None:
            self.detail_title.setText("Select a component")
            self.detail_text.setText("Select a runtime or utility to see available actions.")
            self.open_upstream_button.setEnabled(False)
            self.configure_button.setEnabled(False)
            self.stage_button.setEnabled(False)
            return

        app = APP_BY_KEY[app_key]
        status = self._statuses.get(app_key)
        requirement = self._requirements.get(app_key)
        importance = self._requirement_label(app_key)
        state = self._state_label(app_key, status) if status is not None else "Not checked"
        reason = requirement.reason if requirement is not None else app.description
        detection = status.detection_note if status is not None else "Not checked."
        package = package_for_app(app_key)

        policy_notes = {
            "guide_only": "RommHeld will not modify this system component. Follow the current upstream guide.",
            "console_generated": "This data must be generated from the user's own console and is never downloaded by RommHeld.",
            "prefer_universal_updater": "Use Universal-Updater or the upstream installation process for this multi-file package.",
            "manual_bundle_or_updater": "This package has a multi-file/runtime layout and is not directly staged by RommHeld.",
            "guide_or_universal_updater": "Use the upstream guide or Universal-Updater; RommHeld does not manage this system utility directly.",
            "manual_or_existing": "Verify the installed title on the console or follow the upstream installation procedure.",
            "universal_updater_or_manual": "Prefer Universal-Updater for normal installation. RommHeld can stage a simple verified 3DSX build when one is explicitly supported.",
            "manual_bootstrap": "RommHeld can stage the upstream 3DSX bootstrap; use the application itself for broader homebrew management.",
        }
        policy = policy_notes.get(app.install_policy, app.install_policy)
        runtime_detail = self._runtime_detail(app_key)
        detail = f"{reason}\n\n{detection}\n\n{policy}"
        if runtime_detail:
            detail += f"\n\n{runtime_detail}"
        self.detail_title.setText(f"{app.name} · {importance} · {state}")
        self.detail_text.setText(detail)
        self.open_upstream_button.setEnabled(is_web_url(app.upstream_url))
        self.configure_button.setEnabled(
            app_key == "open-agb-firm" and self._open_agb_config_is_current()
        )
        self.configure_button.setText(
            "Configure open_agb_firm" if app_key == "open-agb-firm" else "Configure"
        )
        self.stage_button.setEnabled(package is not None and self.worker is None)
        self.stage_button.setText(
            f"Stage {package.name} to SD" if package is not None else "Stage to SD"
        )

    def _open_agb_config_is_current(self) -> bool:
        path = open_agb_config_path(self.sd_root)
        if not path.is_file():
            return False
        try:
            return detect_open_agb_config_format(path.read_text(encoding="utf-8")) == "current"
        except OSError:
            return False

    def open_upstream(self) -> None:
        app_key = self._selected_app_key()
        if app_key is None:
            return
        app = APP_BY_KEY[app_key]
        url = app.upstream_url
        if not is_web_url(url):
            QMessageBox.warning(
                self,
                "Invalid upstream URL",
                f"{app.name} does not have a valid HTTP(S) upstream URL configured.",
            )
            return
        if not open_external_url(url):
            QMessageBox.warning(
                self,
                "Unable to open browser",
                f"RommHeld could not open the {app.name} upstream page in your default browser.\n\n"
                f"{url}\n\n"
                "Copy the URL above and open it manually.",
            )

    def configure_selected(self) -> None:
        app_key = self._selected_app_key()
        if app_key != "open-agb-firm":
            return
        dialog = OpenAgbSettingsDialog(self.sd_root, self)
        dialog.exec()
        self.refresh()

    def stage_selected(self) -> None:
        if self.worker is not None:
            return
        app_key = self._selected_app_key()
        package = package_for_app(app_key or "")
        if app_key is None or package is None:
            return
        answer = QMessageBox.question(
            self,
            f"Stage {package.name}",
            f"RommHeld will download the exact {package.asset_name} asset from the latest stable {package.repository} GitHub release, verify the published size and SHA-256 when the release provides one, then stage it to /{package.destination}. Existing files are backed up before replacement. Continue?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.cancel_button.setVisible(True)
        self.operation_status.setText(f"Preparing {package.name}…")
        self.worker = ThreeDSPackageStageWorker(app_key, self.sd_root)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.status_changed.connect(self.operation_status.setText)
        self.worker.completed.connect(self._stage_completed)
        self.worker.failed.connect(self._stage_failed)
        self.worker.cancelled.connect(self._stage_cancelled)
        self.worker.finished.connect(self._worker_finished)
        self.stage_button.setEnabled(False)
        self.worker.start()

    def cancel_staging(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.cancel_button.setEnabled(False)
            self.operation_status.setText("Cancelling package staging…")
            self.worker.cancel()

    def _stage_completed(self, name: str, target: str) -> None:
        self.progress.setValue(100)
        self.operation_status.setText(f"{name} staged to {target}")

    def _stage_failed(self, message: str) -> None:
        self.operation_status.setText(f"Package staging failed: {message}")
        QMessageBox.warning(self, "3DS package staging failed", message)

    def _stage_cancelled(self) -> None:
        self.operation_status.setText("Package staging cancelled.")

    def _worker_finished(self) -> None:
        self.worker = None
        self.cancel_button.setEnabled(True)
        self.cancel_button.setVisible(False)
        self.progress.setVisible(False)
        if self._closing_requested:
            QTimer.singleShot(0, self.close)
            return
        self.refresh()

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            self._closing_requested = True
            self.worker.cancel()
            self.operation_status.setText("Cancelling package staging before closing…")
            event.ignore()
            return
        super().closeEvent(event)
