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
from .three_ds_ftp import ThreeDSFtpSettings
from .three_ds_ftp_inventory import (
    merge_three_ds_app_inventories,
    scan_three_ds_apps_ftp,
)
from .three_ds_packages import download_package, package_for_app, resolve_package, stage_package
from .three_ds_readiness import ReadinessRequirement, evaluate_readiness_statuses
from .three_ds_runtime_details import (
    RETROARCH_CORE_PROFILES,
    scan_retroarch_route,
    scan_twilight_runtime,
)
from .ui_components import AccentButton, SectionHeader, StatusPill, SurfaceCard


NINTENDO_RED = brand_for_platform("3ds").accent
UNIVERSAL_UPDATER_ASSIST_POLICIES = frozenset(
    {
        "prefer_universal_updater",
        "manual_bundle_or_updater",
        "guide_or_universal_updater",
        "universal_updater_or_manual",
    }
)


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


class ThreeDSFtpInventoryWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, settings: ThreeDSFtpSettings):
        super().__init__()
        self.settings = settings

    def run(self) -> None:
        try:
            statuses = scan_three_ds_apps_ftp(
                self.settings,
                cancelled=self.isInterruptionRequested,
            )
        except InterruptedError:
            return
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.completed.emit(statuses)


class ThreeDSReadinessDialog(QDialog):
    """Inspect 3DS readiness and manage only narrowly supported runtime actions."""

    def __init__(
        self,
        sd_root: Path | None,
        *,
        ftp_settings: ThreeDSFtpSettings | None = None,
        target_keys: Iterable[str] = (),
        needs_ftp: bool = True,
        needs_cia_install: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.sd_root = sd_root.expanduser() if sd_root is not None else None
        self.ftp_settings = (
            ftp_settings if ftp_settings is not None and ftp_settings.host.strip() else None
        )
        self.target_keys = tuple(target_keys)
        self.needs_ftp = needs_ftp
        self.needs_cia_install = needs_cia_install
        self.worker: ThreeDSPackageStageWorker | None = None
        self.ftp_scan_worker: ThreeDSFtpInventoryWorker | None = None
        self._assist_target_app_key: str | None = None
        self._closing_requested = False
        self._requirements: dict[str, ReadinessRequirement] = {}
        self._local_statuses: dict[str, ThreeDSAppStatus] = {}
        self._statuses: dict[str, ThreeDSAppStatus] = {}

        self.setWindowTitle("Nintendo 3DS Readiness")
        self.resize(860, 700)
        self.setMinimumSize(760, 600)

        header = SectionHeader(
            "Nintendo 3DS readiness",
            "Check a mounted SD card and/or the live ftpd filesystem, distinguish required components from optional runtimes, and prepare supported homebrew through verified direct staging or the maintained on-console updater path.",
        )

        self.readiness_status = StatusPill("Readiness", "Checking…")
        self.sd_label = QLabel(self._source_summary())
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
            "Detected means RommHeld found reliable mounted-SD, live-FTP, or known SD title-tree evidence. Some installed applications still cannot be proven from filesystem evidence alone and remain a console-confirmation state."
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
        self.stage_button = AccentButton("Prepare on SD", NINTENDO_RED)
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

    def _source_summary(self) -> str:
        sources: list[str] = []
        if self.sd_root is not None:
            sources.append(f"Mounted SD: {self.sd_root}")
        if self.ftp_settings is not None:
            sources.append(
                f"Live FTP: ftp://{self.ftp_settings.host}:{self.ftp_settings.port}"
            )
        return " • ".join(sources) if sources else "No 3DS filesystem source configured"

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
            return "Not detected"
        return "Not detected"

    def _uses_universal_updater_assist(self, app_key: str) -> bool:
        app = APP_BY_KEY[app_key]
        return (
            package_for_app(app_key) is None
            and app.install_policy in UNIVERSAL_UPDATER_ASSIST_POLICIES
        )

    def _universal_updater_detected(self) -> bool:
        status = self._statuses.get("universal-updater")
        return bool(status and status.detected)

    def _runtime_detail(self, app_key: str) -> str:
        if self.sd_root is None:
            if app_key in {"twilight", "retroarch"}:
                return (
                    "Base runtime presence is checked over FTP. Detailed runtime/core layout "
                    "inspection currently requires a mounted SD card."
                )
            return ""
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

    def _empty_statuses(self) -> dict[str, ThreeDSAppStatus]:
        return {
            app.key: ThreeDSAppStatus(app, False, source="unchecked")
            for app in THREE_DS_APPS
        }

    def _report(self):
        return evaluate_readiness_statuses(
            self._statuses,
            self.target_keys,
            root=self.sd_root,
            needs_ftp=self.needs_ftp,
            needs_cia_install=self.needs_cia_install,
            include_utilities=True,
        )

    def _render_inventory(self, selected_key: str | None = None) -> None:
        report = self._report()
        self._requirements = {
            item.requirement.app_key: item.requirement for item in report.items
        }
        if self.ftp_scan_worker is not None and self.ftp_scan_worker.isRunning():
            self.readiness_status.set_value("Checking FTP…")
        elif report.state == "ready":
            self.readiness_status.set_value("Ready")
        elif report.state == "needs_confirmation":
            self.readiness_status.set_value("Confirm on console")
        else:
            self.readiness_status.set_value("Action required")

        if selected_key is None:
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

    def refresh(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        if self.ftp_scan_worker is not None and self.ftp_scan_worker.isRunning():
            return

        selected_key = self._selected_app_key()
        if self.sd_root is not None and self.sd_root.is_dir():
            self._local_statuses = scan_three_ds_apps(self.sd_root)
        else:
            self._local_statuses = self._empty_statuses()
        self._statuses = dict(self._local_statuses)
        self._render_inventory(selected_key)

        if self.ftp_settings is None:
            return

        self.operation_status.setText("Scanning the live 3DS SD filesystem over ftpd…")
        self.ftp_scan_worker = ThreeDSFtpInventoryWorker(self.ftp_settings)
        self.ftp_scan_worker.completed.connect(self._ftp_scan_completed)
        self.ftp_scan_worker.failed.connect(self._ftp_scan_failed)
        self.ftp_scan_worker.finished.connect(self._ftp_scan_finished)
        self.ftp_scan_worker.start()
        self._render_inventory(selected_key)

    def _ftp_scan_completed(self, remote_statuses: object) -> None:
        if not isinstance(remote_statuses, dict):
            return
        self._statuses = merge_three_ds_app_inventories(
            self._local_statuses,
            remote_statuses,
        )
        root_note = (
            f" within configured remote root {self.ftp_settings.remote_root}"
            if self.ftp_settings is not None and self.ftp_settings.remote_root != "/"
            else ""
        )
        self.operation_status.setText(f"Live FTP readiness scan completed{root_note}.")
        self._render_inventory()

    def _ftp_scan_failed(self, message: str) -> None:
        self.operation_status.setText(f"Live FTP readiness scan failed: {message}")
        self._render_inventory()

    def _ftp_scan_finished(self) -> None:
        worker = self.ftp_scan_worker
        self.ftp_scan_worker = None
        if worker is not None:
            worker.deleteLater()
        self._render_inventory()
        self._maybe_finish_close()

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
        updater_assist = self._uses_universal_updater_assist(app_key)

        policy_notes = {
            "guide_only": "Use the maintained upstream guide. RommHeld will not automatically replace boot-chain or exploit-environment files.",
            "console_generated": "Generate this from your own console. RommHeld will not download console-specific system data.",
            "prefer_universal_updater": "Use Universal-Updater for the maintained on-console installation recipe.",
            "manual_bundle_or_updater": "This runtime has a multi-file layout. Use Universal-Updater for the maintained on-console installation recipe.",
            "guide_or_universal_updater": "Use Universal-Updater or the maintained upstream guide; RommHeld will not directly modify this system-sensitive package.",
            "manual_or_existing": "Verify the installed title on the console or use the verified Homebrew Launcher build that RommHeld can prepare on a mounted SD card.",
            "universal_updater_or_manual": "Prefer Universal-Updater for normal installation; RommHeld can directly prepare an explicitly supported verified 3DSX build on a mounted SD card.",
            "manual_bootstrap": "RommHeld can prepare the verified 3DSX bootstrap on a mounted SD card; use the application itself for broader homebrew management.",
        }
        if package is not None:
            if self.sd_root is not None:
                policy = (
                    f"RommHeld can safely prepare the exact upstream {package.asset_name} on this mounted SD card. "
                    "This prepares the Homebrew Launcher build and does not claim that a CIA title is installed."
                )
            else:
                policy = (
                    f"RommHeld can detect {package.name} over FTP, but direct verified package preparation currently requires a mounted SD card."
                )
        elif updater_assist:
            if self._universal_updater_detected():
                policy = (
                    f"Fastest supported path: launch Universal-Updater on the 3DS and search for {app.name}. "
                    "The maintained on-console recipe owns the complex installation steps."
                )
            elif self.sd_root is not None:
                policy = (
                    f"Fastest supported path: RommHeld can prepare Universal-Updater on this mounted SD card. "
                    f"Then launch it on the 3DS and search for {app.name}."
                )
            else:
                policy = (
                    f"Universal-Updater is not currently detected. Mount the SD card if you want RommHeld to prepare its verified bootstrap, or install it on-console and refresh this FTP scan."
                )
        else:
            policy = policy_notes.get(app.install_policy, app.install_policy)

        runtime_detail = self._runtime_detail(app_key)
        detail = f"{reason}\n\n{detection}\n\n{policy}"
        if runtime_detail:
            detail += f"\n\n{runtime_detail}"
        self.detail_title.setText(f"{app.name} · {importance} · {state}")
        self.detail_text.setText(detail)
        self.open_upstream_button.setEnabled(is_web_url(app.upstream_url))
        self.open_upstream_button.setText(
            "Open install guide"
            if app.install_policy in {"guide_only", "console_generated"}
            else "Open upstream"
        )
        self.configure_button.setEnabled(
            app_key == "open-agb-firm" and self._open_agb_config_is_current()
        )
        self.configure_button.setText(
            "Configure open_agb_firm" if app_key == "open-agb-firm" else "Configure"
        )

        scan_busy = self.ftp_scan_worker is not None and self.ftp_scan_worker.isRunning()
        local_stage_available = self.sd_root is not None and self.sd_root.is_dir()
        can_act = (
            package is not None and local_stage_available
        ) or (
            updater_assist
            and (self._universal_updater_detected() or local_stage_available)
        )
        self.stage_button.setEnabled(self.worker is None and not scan_busy and can_act)
        if package is not None and local_stage_available:
            self.stage_button.setText(f"Prepare {package.name}")
        elif package is not None:
            self.stage_button.setText("Mount SD to prepare")
        elif updater_assist and self._universal_updater_detected():
            self.stage_button.setText("Show updater steps")
        elif updater_assist and local_stage_available:
            self.stage_button.setText("Prepare Universal-Updater")
        elif updater_assist:
            self.stage_button.setText("Mount SD to prepare updater")
        elif app.install_policy == "console_generated":
            self.stage_button.setText("Generate on console")
        else:
            self.stage_button.setText("No automatic install")

    def _open_agb_config_is_current(self) -> bool:
        if self.sd_root is None:
            return False
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
        if app_key != "open-agb-firm" or self.sd_root is None:
            return
        dialog = OpenAgbSettingsDialog(self.sd_root, self)
        dialog.exec()
        self.refresh()

    def _start_stage_worker(self, app_key: str) -> None:
        package = package_for_app(app_key)
        if package is None or self.sd_root is None:
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

    def stage_selected(self) -> None:
        if self.worker is not None:
            return
        app_key = self._selected_app_key()
        if app_key is None:
            return
        app = APP_BY_KEY[app_key]
        package = package_for_app(app_key)

        if package is not None:
            if self.sd_root is None:
                return
            answer = QMessageBox.question(
                self,
                f"Prepare {package.name}",
                f"RommHeld will download the exact {package.asset_name} asset from the latest stable {package.repository} GitHub release, verify the published size and SHA-256 when the release provides one, then place it at /{package.destination}. Existing files are backed up before replacement. Continue?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self._assist_target_app_key = None
            self._start_stage_worker(app_key)
            return

        if not self._uses_universal_updater_assist(app_key):
            return
        if self._universal_updater_detected():
            self.operation_status.setText(
                f"On the 3DS, launch Universal-Updater and search for {app.name}. "
                "Use its maintained install recipe, then return here and refresh checks."
            )
            return
        if self.sd_root is None:
            return

        updater = package_for_app("universal-updater")
        if updater is None:
            return
        answer = QMessageBox.question(
            self,
            "Prepare Universal-Updater",
            f"{app.name} uses a complex or system-sensitive install layout. RommHeld will first prepare the verified Universal-Updater 3DSX at /{updater.destination}. Then launch Universal-Updater on the 3DS and search for {app.name}. Continue?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._assist_target_app_key = app_key
        self._start_stage_worker("universal-updater")

    def cancel_staging(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.cancel_button.setEnabled(False)
            self.operation_status.setText("Cancelling package staging…")
            self.worker.cancel()

    def _stage_completed(self, name: str, target: str) -> None:
        self.progress.setValue(100)
        if self._assist_target_app_key:
            app = APP_BY_KEY[self._assist_target_app_key]
            self.operation_status.setText(
                f"Universal-Updater prepared at {target}. On the 3DS, launch it and search for {app.name}."
            )
        else:
            self.operation_status.setText(f"{name} prepared at {target}")

    def _stage_failed(self, message: str) -> None:
        prefix = "Universal-Updater preparation failed" if self._assist_target_app_key else "Package staging failed"
        self.operation_status.setText(f"{prefix}: {message}")
        QMessageBox.warning(self, "3DS package staging failed", message)

    def _stage_cancelled(self) -> None:
        self.operation_status.setText("Package staging cancelled.")

    def _worker_finished(self) -> None:
        self.worker = None
        self.cancel_button.setEnabled(True)
        self.cancel_button.setVisible(False)
        self.progress.setVisible(False)
        if self._closing_requested:
            self._assist_target_app_key = None
            self._maybe_finish_close()
            return
        self.refresh()
        self._assist_target_app_key = None

    def _maybe_finish_close(self) -> None:
        package_running = self.worker is not None and self.worker.isRunning()
        ftp_running = self.ftp_scan_worker is not None and self.ftp_scan_worker.isRunning()
        if self._closing_requested and not package_running and not ftp_running:
            QTimer.singleShot(0, self.close)

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            self._closing_requested = True
            self.worker.cancel()
            self.operation_status.setText("Cancelling package staging before closing…")
            event.ignore()
            return
        if self.ftp_scan_worker is not None and self.ftp_scan_worker.isRunning():
            self._closing_requested = True
            self.ftp_scan_worker.requestInterruption()
            self.operation_status.setText("Stopping FTP readiness scan before closing…")
            event.ignore()
            return
        super().closeEvent(event)
