from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .config import load_config
from .design_tokens import DARK, brand_for_platform
from .library_sources import get_library_source
from .mappings import platform_label
from .models import Game
from .romm import scan_games
from .ui_components import AccentButton, SurfaceCard
from .vita_ftp import VitaFtpSettings
from .vita_ftp_library import VitaFtpCopyWorker, ftp_destination_target
from .vita_library_support import CopyWorker, destination_for_game, game_status, human_size


STATUS_LABELS = {
    "INSTALLED": "Installed",
    "STAGED": "Staged for install",
    "NEW": "Ready to copy",
    "DIFFERENT": "Update available",
    "UNKNOWN": "Destination unavailable",
}


class LocalLibraryWidget(QWidget):
    """Standalone local-ROM library used by Vita and removable-storage workspaces."""

    def __init__(
        self,
        config: dict,
        target_key: str,
        vita: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = dict(config)
        self.target_key = target_key
        self.vita = vita
        self.mappings = dict(config.get("platform_mappings", {}))
        self.games: list[Game] = []
        self.filtered_games: list[Game] = []
        self.worker: CopyWorker | VitaFtpCopyWorker | None = None
        self._library_root: Path | None = None
        self._status_cache: dict[Path, tuple[str, str]] = {}

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search games")
        self.search.setClearButtonEnabled(True)
        self.platforms = QComboBox()
        self.platforms.addItem("All platforms", None)
        self.status_filter = QComboBox()
        self.status_filter.addItems(
            [
                "All games",
                "Ready to copy",
                "Installed",
                "Staged for install",
                "Update available",
                "Destination unavailable",
            ]
        )
        self.vita_transport = QComboBox()
        self.vita_transport.addItem("VitaShell USB", "usb")
        self.vita_transport.addItem("VitaShell FTP", "ftp")
        saved_ftp = load_config().get("devices", {}).get("vita_ftp", {})
        if vita is None and str(saved_ftp.get("host", "")).strip():
            self.vita_transport.setCurrentIndex(1)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setToolTip("Rescan the configured local library")

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.refresh_button)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        filters.addWidget(self.platforms)
        filters.addWidget(self.status_filter)
        filters.addWidget(self.vita_transport)
        filters.addStretch(1)

        self.source_label = QLabel()
        self.source_label.setWordWrap(True)
        self.source_label.setStyleSheet(f"color:{DARK.text_secondary};font-size:10px;")

        self.game_list = QListWidget()
        self.game_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.game_list.setSpacing(1)

        self.selection_label = QLabel("0 selected")
        self.selection_label.setStyleSheet(f"color:{DARK.text_secondary};")
        self.destination_label = QLabel("Select a game to see where it will go.")
        self.destination_label.setWordWrap(True)
        self.destination_label.setStyleSheet(f"color:{DARK.text_secondary};")
        self.copy_button = AccentButton(
            "Copy to Vita",
            brand_for_platform("vita").accent,
        )
        self.copy_button.setEnabled(False)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.transfer_status = QLabel()
        self.transfer_status.setWordWrap(True)
        self.transfer_status.setVisible(False)
        self.transfer_status.setStyleSheet(f"color:{DARK.text_secondary};")
        self.cancel_button = QPushButton("Cancel transfer")
        self.cancel_button.setVisible(False)

        card = SurfaceCard()
        card.content.addLayout(search_row)
        card.content.addLayout(filters)
        card.content.addWidget(self.source_label)
        card.content.addWidget(self.game_list, 1)

        summary = QHBoxLayout()
        summary.setSpacing(10)
        summary.addWidget(self.selection_label)
        summary.addWidget(self.destination_label, 1)
        summary.addWidget(self.copy_button)
        card.content.addLayout(summary)
        card.content.addWidget(self.progress)

        transfer_row = QHBoxLayout()
        transfer_row.addWidget(self.transfer_status, 1)
        transfer_row.addWidget(self.cancel_button)
        card.content.addLayout(transfer_row)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(card, 1)

        self.refresh_button.clicked.connect(self.refresh_library)
        self.search.textChanged.connect(self._apply_filters)
        self.platforms.currentIndexChanged.connect(self._apply_filters)
        self.status_filter.currentIndexChanged.connect(self._apply_filters)
        self.vita_transport.currentIndexChanged.connect(self._transport_changed)
        self.game_list.itemSelectionChanged.connect(self.update_summary)
        self.copy_button.clicked.connect(self.copy_selected)
        self.cancel_button.clicked.connect(self.cancel_copy)

        self.set_target(target_key, vita)
        self._transport_changed(refresh=False)
        self.refresh_library()

    def set_config(self, config: dict) -> None:
        self.config = dict(config)
        self.mappings = dict(config.get("platform_mappings", {}))
        self._status_cache.clear()

    def set_target(self, target_key: str, vita: Path | None = None) -> None:
        if self.target_key != target_key or self.vita != vita:
            self._status_cache.clear()
        self.target_key = target_key
        self.vita = vita
        is_vita = target_key == "vita"
        self.vita_transport.setVisible(is_vita)
        self.status_filter.setVisible(is_vita)
        self.copy_button.setVisible(is_vita)
        self._sync_status_filter()
        self._apply_filters()

    def set_vita(self, vita: Path | None) -> None:
        if self.vita != vita:
            self._status_cache.clear()
        self.vita = vita
        if self.target_key == "vita":
            self._sync_status_filter()
            self._apply_filters()

    def _using_ftp(self) -> bool:
        return self.target_key == "vita" and self.vita_transport.currentData() == "ftp"

    def _status_filter_available(self) -> bool:
        return self.target_key == "vita" and not self._using_ftp() and self.vita is not None

    def _sync_status_filter(self) -> None:
        available = self._status_filter_available()
        if not available and self.status_filter.currentIndex() != 0:
            self.status_filter.blockSignals(True)
            self.status_filter.setCurrentIndex(0)
            self.status_filter.blockSignals(False)
        worker_running = self.worker is not None and self.worker.isRunning()
        self.status_filter.setEnabled(available and not worker_running)
        if self.target_key != "vita":
            tooltip = ""
        elif self._using_ftp():
            tooltip = (
                "Install state is checked during FTP transfer because VitaShell FTP does not expose a cheap bulk-status query."
            )
        elif self.vita is None:
            tooltip = "Connect the Vita through VitaShell USB to filter by installed state."
        else:
            tooltip = "Choose a status filter to inspect files detected on the mounted Vita filesystem."
        self.status_filter.setToolTip(tooltip)

    def _ftp_settings(self) -> VitaFtpSettings:
        saved = load_config().get("devices", {}).get("vita_ftp", {})
        host = str(saved.get("host", "")).strip()
        if not host:
            raise ValueError(
                "VitaShell FTP is not configured. Open Device → Send file, choose VitaShell FTP, and enter the IP address and port shown by VitaShell."
            )
        try:
            port = int(saved.get("port", 1337))
            if not 1 <= port <= 65535:
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise ValueError("The saved VitaShell FTP port is invalid.") from exc
        return VitaFtpSettings(host=host, port=port)

    def _ftp_ready(self) -> bool:
        try:
            self._ftp_settings()
            return True
        except ValueError:
            return False

    def _transport_changed(self, _index: int | None = None, *, refresh: bool = True) -> None:
        if self.target_key != "vita":
            return
        self._status_cache.clear()
        using_ftp = self._using_ftp()
        self._sync_status_filter()
        self.copy_button.setText("Copy via VitaShell FTP" if using_ftp else "Copy to Vita")
        if refresh:
            self._apply_filters()
        else:
            self.update_summary()

    def refresh_library(self) -> None:
        """Rescan the configured source, then render the current filters."""
        self._status_cache.clear()
        source = get_library_source(self.config)
        if source.mode != "local":
            self._library_root = None
            self.games = []
            self.filtered_games = []
            self._render_games()
            self.source_label.setText("This workspace is configured for RomM, not a local library.")
            self.source_label.setToolTip("")
            self.destination_label.setText("Choose a local source in Settings to browse local games here.")
            self.update_summary()
            return

        root = Path(source.local_root or self.config.get("romm_root", "")).expanduser()
        self._library_root = root
        self.games = list(scan_games(root)) if root.is_dir() else []
        self._rebuild_platform_filter()
        self._apply_filters()

    def _rebuild_platform_filter(self) -> None:
        current = self.platforms.currentData() if self.platforms.count() else None
        self.platforms.blockSignals(True)
        self.platforms.clear()
        self.platforms.addItem("All platforms", None)
        platform_keys = sorted(
            {game.source_platform for game in self.games},
            key=lambda value: platform_label(value).lower(),
        )
        for key in platform_keys:
            self.platforms.addItem(platform_label(key), key)
        index = self.platforms.findData(current) if current is not None else 0
        self.platforms.setCurrentIndex(index if index >= 0 else 0)
        self.platforms.blockSignals(False)

    def _apply_filters(self) -> None:
        """Filter the in-memory scan without repeatedly walking the ROM tree."""
        query = self.search.text().strip().casefold()
        platform = self.platforms.currentData()
        wanted = self.status_filter.currentText()
        filtered: list[Game] = []
        for game in self.games:
            if query and query not in game.name.casefold():
                continue
            if platform is not None and game.source_platform != platform:
                continue
            if wanted != "All games":
                state, _detail = self._game_status(game)
                if wanted == "Ready to copy" and state != "NEW":
                    continue
                if wanted == "Installed" and state != "INSTALLED":
                    continue
                if wanted == "Staged for install" and state != "STAGED":
                    continue
                if wanted == "Update available" and state != "DIFFERENT":
                    continue
                if wanted == "Destination unavailable" and state != "UNKNOWN":
                    continue
            filtered.append(game)
        self.filtered_games = filtered
        self._render_games()
        self._update_source_summary()
        self.update_summary()

    def _render_games(self) -> None:
        self.game_list.clear()
        show_status = (
            self._status_filter_available()
            and self.status_filter.currentText() != "All games"
        )
        for game in self.filtered_games:
            metadata = f"{platform_label(game.source_platform)} • {human_size(game.size)}"
            if show_status:
                state, detail = self._game_status(game)
                metadata += f" • {STATUS_LABELS.get(state, state.title())}"
            elif self.target_key != "vita":
                detail = "Destination is managed from the Device workflow"
            elif self._using_ftp():
                detail = "VitaShell FTP checks the remote file when transfer starts"
            elif self.vita is None:
                detail = "Connect the Vita through VitaShell USB to inspect installed state"
            else:
                detail = "Choose a status filter to inspect the current Vita destination state"
            item = QListWidgetItem(f"{game.name}\n{metadata}")
            item.setData(Qt.ItemDataRole.UserRole, game)
            item.setToolTip(detail)
            self.game_list.addItem(item)

        if not self.filtered_games:
            item = QListWidgetItem(self._empty_message())
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.game_list.addItem(item)

    def _empty_message(self) -> str:
        if not self.games:
            if self._library_root is None:
                return "No local library is active. Choose a local source in Settings."
            if not self._library_root.is_dir():
                return "The local library folder is unavailable. Reconnect it or choose another source in Settings."
            return "No games were found in this local library. Check the folder or choose another source in Settings."
        return "No games match the current search and filters. Clear the search or adjust the filters."

    def _update_source_summary(self) -> None:
        if self._library_root is None:
            return
        target_label = "PlayStation Vita" if self.target_key == "vita" else "Nintendo DS"
        shown = len(self.filtered_games)
        total = len(self.games)
        count = f"{shown} of {total} games" if shown != total else f"{total} games"
        transport = (
            " • VitaShell FTP"
            if self._using_ftp()
            else " • VitaShell USB"
            if self.target_key == "vita"
            else ""
        )
        self.source_label.setText(f"Local library • {count} • {target_label}{transport}")
        self.source_label.setToolTip(str(self._library_root))

    def _game_status(self, game: Game) -> tuple[str, str]:
        if self.target_key != "vita":
            return "UNKNOWN", "Destination is managed from the Device workflow"
        if self._using_ftp():
            return "UNKNOWN", "VitaShell FTP checks the remote file when transfer starts"
        cached = self._status_cache.get(game.path)
        if cached is not None:
            return cached
        try:
            result = game_status(self.vita, game, self.mappings)
        except Exception:
            result = ("UNKNOWN", "Unable to inspect the current Vita destination")
        self._status_cache[game.path] = result
        return result

    def selected_games(self) -> list[Game]:
        result: list[Game] = []
        for item in self.game_list.selectedItems():
            game = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(game, Game):
                result.append(game)
        return result

    def update_summary(self) -> None:
        selected = self.selected_games()
        total = sum(game.size for game in selected)
        is_vita = self.target_key == "vita"
        worker_running = self.worker is not None and self.worker.isRunning()
        transport_ready = self._ftp_ready() if self._using_ftp() else self.vita is not None
        self.copy_button.setVisible(is_vita)
        self.copy_button.setEnabled(
            is_vita and transport_ready and bool(selected) and not worker_running
        )
        self.selection_label.setText(
            f"{len(selected)} selected • {human_size(total)}" if selected else "No games selected"
        )
        self.destination_label.setToolTip("")

        if len(selected) != 1:
            if selected and is_vita:
                if not transport_ready:
                    self.destination_label.setText(
                        "Configure VitaShell FTP in Device → Send file."
                        if self._using_ftp()
                        else "Connect the Vita through VitaShell USB to copy the selected games."
                    )
                else:
                    method = "VitaShell FTP" if self._using_ftp() else "VitaShell USB"
                    self.destination_label.setText(
                        f"Ready to copy {len(selected)} games through {method}."
                    )
            elif selected:
                self.destination_label.setText("Destination is chosen from the Device workflow.")
            else:
                self.destination_label.setText("Select a game to see where it will go.")
            return

        game = selected[0]
        if not is_vita:
            self.destination_label.setText("Destination is chosen from the Device workflow.")
            return
        if not transport_ready:
            self.destination_label.setText(
                "Configure VitaShell FTP in Device → Send file."
                if self._using_ftp()
                else "Connect the Vita through VitaShell USB to copy this game."
            )
            return
        if self._using_ftp():
            label, target, _mode = ftp_destination_target(game, self.mappings)
            self.destination_label.setText(f"Copies to {label}")
            self.destination_label.setToolTip(target or "Destination review required")
        else:
            label, path, _mode = destination_for_game(self.vita, game, self.mappings)
            self.destination_label.setText(f"Copies to {label}")
            self.destination_label.setToolTip(str(path))

    def copy_selected(self) -> None:
        if self.target_key != "vita":
            QMessageBox.information(
                self,
                "Use the device workflow",
                "Direct library copying is currently available for the Vita workspace only.",
            )
            return
        if self.worker is not None and self.worker.isRunning():
            return

        selected = self.selected_games()
        if not selected:
            QMessageBox.information(self, "Nothing selected", "Select one or more games first.")
            return

        if self._using_ftp():
            self._copy_selected_ftp(selected)
        else:
            self._copy_selected_usb(selected)

    def _copy_selected_ftp(self, selected: list[Game]) -> None:
        try:
            settings = self._ftp_settings()
        except ValueError as exc:
            QMessageBox.warning(self, "VitaShell FTP not configured", str(exc))
            return

        jobs = []
        review: list[str] = []
        for game in selected:
            label, destination, mode = ftp_destination_target(game, self.mappings)
            if mode == "unknown" or not destination:
                review.append(f"{game.name} ({game.source_platform})")
                continue
            jobs.append((game, destination, label))

        if review:
            QMessageBox.warning(
                self,
                "Destination review required",
                "These games could not be mapped safely and were not queued:\n\n"
                + "\n".join(review[:20])
                + ("\n…" if len(review) > 20 else ""),
            )
        if not jobs:
            QMessageBox.information(
                self,
                "Nothing to copy",
                "No selected games have a safe Vita destination.",
            )
            return

        total = sum(game.size for game, *_rest in jobs)
        if (
            QMessageBox.question(
                self,
                "Confirm FTP copy",
                f"Process {len(jobs)} game(s), {human_size(total)}, through VitaShell FTP?\n\n"
                "Existing same-size files will be skipped. Different-size files are replaced only after the new upload verifies successfully. "
                "VitaShell FTP does not report reliable free-space information, so capacity cannot be pre-checked on this route.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        self._set_transfer_running(True)
        self.progress.setValue(0)
        self.worker = VitaFtpCopyWorker(settings, jobs)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._copy_finished)
        self.worker.failed.connect(self._copy_failed)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _copy_selected_usb(self, selected: list[Game]) -> None:
        if self.vita is None:
            QMessageBox.warning(
                self,
                "Vita not connected",
                "Connect the Vita through VitaShell USB first, or select VitaShell FTP.",
            )
            return

        jobs = []
        review: list[str] = []
        replacements: list[str] = []
        for game in selected:
            state, _detail = self._game_status(game)
            if state in {"INSTALLED", "STAGED"}:
                continue
            label, destination, mode = destination_for_game(self.vita, game, self.mappings)
            if mode == "unknown":
                review.append(f"{game.name} ({game.source_platform})")
                continue
            if state == "DIFFERENT":
                replacements.append(game.name)
            jobs.append((game, destination, mode, label))

        if review:
            QMessageBox.warning(
                self,
                "Destination review required",
                "These games could not be mapped safely and were not queued:\n\n"
                + "\n".join(review[:20])
                + ("\n…" if len(review) > 20 else ""),
            )
        if not jobs:
            QMessageBox.information(
                self,
                "Nothing to copy",
                "Everything selected is already present or unmapped.",
            )
            return

        total = sum(game.size for game, *_rest in jobs)
        from .vita import free_space

        try:
            available = free_space(self.vita)
        except OSError as exc:
            QMessageBox.critical(self, "Storage check failed", str(exc))
            return
        if total > available:
            QMessageBox.warning(
                self,
                "Not enough Vita storage",
                f"Selected transfers need {human_size(total)}, but the Vita has only {human_size(available)} free.",
            )
            return

        replacement_note = ""
        if replacements:
            replacement_note = (
                f"\n\n{len(replacements)} destination file(s) have different sizes and will be replaced. "
                "Each existing file is preserved until its replacement has copied successfully."
            )
        if (
            QMessageBox.question(
                self,
                "Confirm replacements" if replacements else "Confirm copy",
                f"Process {len(jobs)} game(s), {human_size(total)}?"
                f"{replacement_note}\n\nAlready-complete files will be skipped.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        self._set_transfer_running(True)
        self.progress.setValue(0)
        self.worker = CopyWorker(jobs)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._copy_finished)
        self.worker.failed.connect(self._copy_failed)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def cancel_copy(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self.transfer_status.setText("Cancelling transfer…")

    def _set_transfer_running(self, running: bool) -> None:
        self.refresh_button.setEnabled(not running)
        self.search.setEnabled(not running)
        self.platforms.setEnabled(not running)
        self.status_filter.setEnabled(not running and self._status_filter_available())
        self.vita_transport.setEnabled(not running)
        self.game_list.setEnabled(not running)
        self.progress.setVisible(running)
        self.transfer_status.setVisible(running)
        self.cancel_button.setVisible(running)
        self.cancel_button.setEnabled(running)
        if running:
            self.copy_button.setEnabled(False)
            self.transfer_status.setText("Preparing transfer…")
        else:
            self.update_summary()

    def _on_progress(self, value: int, message: str, detail: str) -> None:
        self.progress.setValue(value)
        self.transfer_status.setText(f"{message} • {detail}")

    def _copy_finished(self, copied: int, skipped: int, cancelled: int) -> None:
        self._set_transfer_running(False)
        self._status_cache.clear()
        self._apply_filters()
        self.transfer_status.setVisible(True)
        if cancelled:
            self.transfer_status.setText(
                f"Transfer stopped • {copied} copied • {skipped} skipped • {cancelled} cancelled"
            )
        else:
            self.transfer_status.setText(f"Transfer complete • {copied} copied • {skipped} skipped")

    def _copy_failed(self, message: str) -> None:
        self._set_transfer_running(False)
        QMessageBox.critical(self, "Transfer failed", message)

    def _worker_finished(self) -> None:
        self.worker = None
        self.update_summary()

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        super().closeEvent(event)


__all__ = ["LocalLibraryWidget"]