from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from .design_tokens import DARK, brand_for_platform
from .library_sources import get_library_source
from .mappings import normalize_platform_slug, platform_label
from .models import Game
from .romm_remote import RomMRemoteGame
from .three_ds_apps import APP_BY_KEY
from .three_ds_ftp import ThreeDSFtpSettings
from .three_ds_manager import ThreeDSTransferWorker
from .three_ds_readiness import TARGET_RUNTIME_APPS, evaluate_target_runtime
from .three_ds_storage import configured_3ds_storage_root
from .three_ds_storage_worker import ThreeDSMountedTransferWorker
from .three_ds_targets import default_destination
from .ui_components import AccentButton, SectionHeader, StatusPill, SurfaceCard


NINTENDO_RED = brand_for_platform("3ds").accent
LibraryGame = RomMRemoteGame | Game


def _platform_slug(game: LibraryGame) -> str:
    if isinstance(game, RomMRemoteGame):
        return str(game.platform_slug or game.platform).strip().lower()
    return normalize_platform_slug(game.source_platform)


def _platform_name(game: LibraryGame) -> str:
    if isinstance(game, RomMRemoteGame):
        return game.platform
    return platform_label(_platform_slug(game))


def _filename(game: LibraryGame) -> str:
    return game.filename if isinstance(game, RomMRemoteGame) else game.path.name


class ThreeDSFilesystemDeployDialog(QDialog):
    """Choose mounted-SD or ftpd transport after a 3DS filesystem target is known."""

    def __init__(self, config: dict, game: LibraryGame, target_key: str, parent=None):
        super().__init__(parent)
        self.config = config
        self.game = game
        self.target_key = target_key
        self.library_source = get_library_source(config)
        self.storage_root = configured_3ds_storage_root(config)
        self.worker: QThread | None = None
        self._last_result: str | None = None
        self._active_transport = ""
        self._closing_requested = False

        saved = config.get("devices", {}).get("3ds", {})
        self._ftp_host = str(saved.get("host", "")).strip()
        try:
            self._ftp_port = int(saved.get("port", 5000))
        except (TypeError, ValueError):
            self._ftp_port = 5000

        self.platform_slug = _platform_slug(game)
        self.destination = default_destination(
            target_key,
            self.platform_slug,
            _filename(game),
        )

        self.setWindowTitle("Deploy to Nintendo 3DS")
        self.resize(720, 540)
        self.setMinimumSize(620, 480)

        header = SectionHeader(
            "Deploy to Nintendo 3DS",
            "The game, runtime and destination are already selected. Choose how the file should reach the console storage.",
        )

        summary = SurfaceCard()
        summary.content.addWidget(self._card_title(game.name))
        summary.content.addWidget(
            self._secondary(
                f"{_platform_name(game)} · {game.size:,} bytes\nDestination: {self.destination}"
            )
        )
        self.runtime_status = StatusPill("Runtime", "Not checked")
        self.runtime_detail = QLabel()
        self.runtime_detail.setWordWrap(True)
        self.runtime_detail.setStyleSheet(f"color:{DARK.text_secondary};")
        runtime_form = QFormLayout()
        runtime_form.setContentsMargins(0, 4, 0, 0)
        runtime_form.addRow(self.runtime_status, self.runtime_detail)
        summary.content.addLayout(runtime_form)

        route_card = SurfaceCard()
        route_card.content.addWidget(self._card_title("Transfer method"))
        route_card.content.addWidget(
            self._secondary(
                "Mounted SD is the direct/offline route when the 3DS SD or microSD card is in a computer or card reader. ftpd is the wireless live-console route. RommHeld does not label the card-reader route as USB because the console does not expose standard USB mass storage."
            )
        )
        self.transport_combo = QComboBox()
        if self.storage_root is not None:
            self.transport_combo.addItem("Mounted SD card · Direct / offline", "sd")
        if self._ftp_host:
            self.transport_combo.addItem("ftpd · Wireless / live console", "ftp")
        if not self.transport_combo.count():
            self.transport_combo.addItem("No filesystem route configured", "")
        self.transport_combo.currentIndexChanged.connect(self._transport_changed)
        route_card.content.addWidget(self.transport_combo)

        self.route_status = StatusPill("Route", "Not ready")
        self.route_detail = QLabel()
        self.route_detail.setWordWrap(True)
        self.route_detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow(self.route_status, self.route_detail)
        route_card.content.addLayout(form)

        activity = SurfaceCard()
        activity.content.addWidget(self._card_title("Transfer"))
        self.status = QLabel("Choose an available transfer method.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color:{DARK.text_secondary};")
        activity.content.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        activity.content.addWidget(self.progress)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_button = QPushButton("Cancel transfer")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_transfer)
        self.deploy_button = AccentButton("Deploy", NINTENDO_RED)
        self.deploy_button.clicked.connect(self.start_transfer)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.deploy_button)
        activity.content.addLayout(actions)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        close_row.addWidget(close)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(header)
        layout.addWidget(summary)
        layout.addWidget(route_card)
        layout.addWidget(activity)
        layout.addStretch(1)
        layout.addLayout(close_row)

        self._refresh_runtime_preflight()
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
        label.setStyleSheet(
            f"color:{DARK.text_secondary};background:transparent;"
        )
        return label

    def _refresh_runtime_preflight(self) -> None:
        app_key = TARGET_RUNTIME_APPS.get(self.target_key)
        if app_key is None:
            self.runtime_status.set_value("Not required")
            self.runtime_detail.setText(
                "This filesystem target does not require a separately managed emulator/runtime."
            )
            return

        app_name = APP_BY_KEY[app_key].name
        root = configured_3ds_storage_root(self.config)
        self.storage_root = root
        if root is None:
            self.runtime_status.set_value("Not checked")
            self.runtime_detail.setText(
                f"No mounted 3DS SD card is currently available to inspect {app_name}. "
                "The file can still be transferred with ftpd, but confirm the selected runtime on the console before expecting it to launch."
            )
            return

        preflight = evaluate_target_runtime(root, self.target_key)
        if preflight is None:
            self.runtime_status.set_value("Not required")
            self.runtime_detail.setText("No separate runtime check is required for this target.")
            return
        if preflight.state == "detected":
            self.runtime_status.set_value("Detected")
        elif preflight.state == "confirm_on_console":
            self.runtime_status.set_value("Confirm on console")
        else:
            self.runtime_status.set_value("Runtime missing")
        self.runtime_detail.setText(preflight.note)

    def _selected_transport(self) -> str:
        return str(self.transport_combo.currentData() or "")

    def _transport_changed(
        self,
        _index: int | None = None,
        *,
        update_activity: bool = True,
    ) -> None:
        transport = self._selected_transport()
        if transport == "sd" and self.storage_root is not None:
            self.route_status.set_value("Mounted SD")
            self.route_detail.setText(str(self.storage_root))
            if update_activity:
                self.status.setText(
                    "Ready for a safe direct copy. Keep the card mounted until the transfer completes, then eject it cleanly before returning it to the 3DS."
                )
            self.deploy_button.setEnabled(True)
        elif transport == "ftp" and self._ftp_host:
            self.route_status.set_value("ftpd")
            self.route_detail.setText(f"ftp://{self._ftp_host}:{self._ftp_port}")
            if update_activity:
                self.status.setText(
                    "Ready to connect. Open ftpd on the Nintendo 3DS and leave it running during the transfer."
                )
            self.deploy_button.setEnabled(True)
        else:
            self.route_status.set_value("Setup required")
            self.route_detail.setText(
                "Configure a mounted 3DS SD card or ftpd from the Device page first."
            )
            if update_activity:
                self.status.setText(
                    "No Nintendo 3DS filesystem transfer route is currently available."
                )
            self.deploy_button.setEnabled(False)

    def _ftp_settings(self) -> ThreeDSFtpSettings:
        saved = self.config.get("devices", {}).get("3ds", {})
        if not self._ftp_host:
            raise ValueError("Nintendo 3DS ftpd is not configured.")
        if not 1 <= self._ftp_port <= 65535:
            raise ValueError("Nintendo 3DS FTP port must be between 1 and 65535.")
        return ThreeDSFtpSettings(
            host=self._ftp_host,
            port=self._ftp_port,
            username=str(saved.get("username", "anonymous")).strip() or "anonymous",
            password=str(saved.get("password", "")),
            remote_root=str(saved.get("remote_root", "/")).strip() or "/",
        )

    def _transfer_source(
        self,
    ) -> tuple[Path | None, RomMRemoteGame | None, str, str]:
        if isinstance(self.game, RomMRemoteGame):
            return (
                None,
                self.game,
                self.library_source.romm_url,
                self.library_source.api_token,
            )
        if not self.game.path.is_file():
            raise FileNotFoundError(
                "The selected local file is no longer available. Refresh the Library and retry."
            )
        return self.game.path, None, "", ""

    def start_transfer(
        self,
        _checked: bool = False,
        *,
        overwrite: bool = False,
    ) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        transport = self._selected_transport()
        if transport not in {"sd", "ftp"}:
            return

        try:
            source, remote_game, romm_url, romm_token = self._transfer_source()
        except (FileNotFoundError, ValueError) as exc:
            self._reset_after_failure(str(exc))
            return

        self._last_result = None
        self._active_transport = transport
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.transport_combo.setEnabled(False)
        self.deploy_button.setEnabled(False)
        self.cancel_button.setVisible(True)
        self.cancel_button.setEnabled(True)
        self.status.setText(
            f"Preparing verified replacement for {self.game.name}…"
            if overwrite
            else f"Checking destination for {self.game.name}…"
        )

        if transport == "sd":
            root = configured_3ds_storage_root(self.config)
            if root is None:
                self._reset_after_failure(
                    "The configured Nintendo 3DS SD card is no longer mounted or no longer validates as a 3DS root."
                )
                return
            worker: QThread = ThreeDSMountedTransferWorker(
                root,
                source,
                self.destination,
                remote_game=remote_game,
                romm_url=romm_url,
                romm_token=romm_token,
                overwrite=overwrite,
            )
        else:
            try:
                settings = self._ftp_settings()
            except ValueError as exc:
                self._reset_after_failure(str(exc))
                return
            worker = ThreeDSTransferWorker(
                settings,
                source,
                self.destination,
                remote_game=remote_game,
                romm_url=romm_url,
                romm_token=romm_token,
                overwrite=overwrite,
            )

        self.worker = worker
        worker.status_changed.connect(self.status.setText)
        worker.progress.connect(self._progress)
        worker.completed.connect(self._completed)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._finished)
        worker.start()

    def _progress(self, done: int) -> None:
        total = int(self.game.size)
        if total > 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(min(100, int(done * 100 / total)))
        else:
            self.progress.setRange(0, 0)

    def _completed(self, result: str) -> None:
        self._last_result = result
        messages = {
            "copied": "Transfer complete. The final destination was size verified.",
            "resumed": "The matching RommHeld FTP stage resumed, verified, and moved into place.",
            "skipped": "The destination already contains the same-size file. No download or replacement was needed.",
            "different": "A different-size file already exists. Nothing was changed.",
            "cancelled": "Transfer cancelled. The existing destination was preserved.",
        }
        self.status.setText(messages.get(result, result))

    def _failed(self, message: str) -> None:
        self._last_result = None
        prefix = (
            "ftpd transfer failed. Confirm ftpd is open on the 3DS and that the saved IP address and port still match. "
            if self._active_transport == "ftp"
            else "Mounted-SD transfer failed. Confirm the card is still mounted and writable. "
        )
        self.status.setText(prefix + message)

    def _finished(self) -> None:
        result = self._last_result
        self.worker = None
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        self.cancel_button.setVisible(False)
        self.transport_combo.setEnabled(True)

        if self._closing_requested:
            QTimer.singleShot(0, self.close)
            return

        if result == "different":
            answer = QMessageBox.question(
                self,
                "Replace existing 3DS file?",
                "The destination contains a different-size file. Replace it? RommHeld stages the new file and keeps the existing destination until the replacement has completed safely.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.start_transfer(overwrite=True)
                return
        self._refresh_runtime_preflight()
        self._transport_changed(update_activity=False)

    def _reset_after_failure(self, message: str) -> None:
        self.worker = None
        self.progress.setVisible(False)
        self.cancel_button.setVisible(False)
        self.transport_combo.setEnabled(True)
        self.status.setText(message)
        self.deploy_button.setEnabled(bool(self._selected_transport()))

    def cancel_transfer(self) -> None:
        worker = self.worker
        if worker is not None and worker.isRunning() and hasattr(worker, "cancel"):
            worker.cancel()
            self.cancel_button.setEnabled(False)
            self.status.setText("Cancelling transfer…")

    def closeEvent(self, event: QCloseEvent) -> None:
        worker = self.worker
        if worker is not None and worker.isRunning():
            self._closing_requested = True
            if hasattr(worker, "cancel"):
                worker.cancel()
            self.cancel_button.setEnabled(False)
            self.status.setText("Cancelling the active transfer before closing…")
            event.ignore()
            return
        super().closeEvent(event)


__all__ = ["ThreeDSFilesystemDeployDialog"]
