from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
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

from .design_tokens import DARK, brand_for_platform
from .library_sources import get_library_source
from .mappings import platform_label
from .models import Game
from .romm import scan_games
from .ui_components import AccentButton, SurfaceCard
from .vita_library_support import CopyWorker, destination_for_game, game_status, human_size


STATUS_SYMBOLS = {"INSTALLED": "✓", "NEW": "↓", "DIFFERENT": "↻", "UNKNOWN": "?"}


class LocalLibraryWidget(QWidget):
    """Standalone local-ROM library used by Vita and removable-storage workspaces.

    The original library lived inside the Vita-specific MainWindow. This widget
    keeps the same filtering and Vita copy semantics without requiring the
    application shell to inherit from that legacy window.
    """

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
        self.worker: CopyWorker | None = None

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search games…")
        self.platforms = QComboBox()
        self.platforms.addItem("All platforms")
        self.status_filter = QComboBox()
        self.status_filter.addItems(
            ["All games", "Not installed", "Installed", "Different", "Unknown"]
        )
        self.view_mode = QComboBox()
        self.view_mode.addItems(["List", "Tiles"])
        self.refresh_button = QPushButton("Refresh")

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(self.search, 1)
        controls.addWidget(self.platforms)
        controls.addWidget(self.status_filter)
        controls.addWidget(self.view_mode)
        controls.addWidget(self.refresh_button)

        self.source_label = QLabel()
        self.source_label.setWordWrap(True)
        self.source_label.setStyleSheet(f"color:{DARK.text_secondary};")

        self.game_list = QListWidget()
        self.game_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

        self.selection_label = QLabel("0 selected")
        self.selection_label.setStyleSheet(f"color:{DARK.text_secondary};")
        self.destination_label = QLabel("Select a game to see its destination.")
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
        card.content.addLayout(controls)
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
        self.search.textChanged.connect(self.refresh_library)
        self.platforms.currentIndexChanged.connect(self.refresh_library)
        self.status_filter.currentIndexChanged.connect(self.refresh_library)
        self.view_mode.currentIndexChanged.connect(self.apply_view_mode)
        self.game_list.itemSelectionChanged.connect(self.update_summary)
        self.copy_button.clicked.connect(self.copy_selected)
        self.cancel_button.clicked.connect(self.cancel_copy)

        self.set_target(target_key, vita)
        self.refresh_library()

    def set_config(self, config: dict) -> None:
        self.config = dict(config)
        self.mappings = dict(config.get("platform_mappings", {}))

    def set_target(self, target_key: str, vita: Path | None = None) -> None:
        self.target_key = target_key
        self.vita = vita
        is_vita = target_key == "vita"
        self.status_filter.setEnabled(is_vita)
        self.copy_button.setVisible(is_vita)
        if not is_vita:
            self.status_filter.setCurrentIndex(0)
        self.update_summary()

    def set_vita(self, vita: Path | None) -> None:
        self.vita = vita
        if self.target_key == "vita":
            self.refresh_library()

    def refresh_library(self) -> None:
        source = get_library_source(self.config)
        if source.mode != "local":
            self.games = []
            self.filtered_games = []
            self.game_list.clear()
            self.source_label.setText(
                "RomM server selected • this workspace does not yet expose a remote library view."
            )
            self.destination_label.setText("No local library is substituted.")
            self.update_summary()
            return

        root = Path(source.local_root or self.config.get("romm_root", "")).expanduser()
        self.games = list(scan_games(root)) if root.is_dir() else []

        current = self.platforms.currentText() if self.platforms.count() else "All platforms"
        self.platforms.blockSignals(True)
        self.platforms.clear()
        self.platforms.addItem("All platforms")
        self.platforms.addItems(
            sorted(
                {game.source_platform for game in self.games},
                key=lambda value: platform_label(value).lower(),
            )
        )
        index = self.platforms.findText(current)
        self.platforms.setCurrentIndex(index if index >= 0 else 0)
        self.platforms.blockSignals(False)

        query = self.search.text().strip().lower()
        platform = self.platforms.currentText()
        wanted = self.status_filter.currentText()
        filtered: list[Game] = []
        for game in self.games:
            if query and query not in game.name.lower():
                continue
            if platform != "All platforms" and game.source_platform != platform:
                continue
            state, _detail = self._game_status(game)
            if wanted == "Not installed" and state != "NEW":
                continue
            if wanted == "Installed" and state != "INSTALLED":
                continue
            if wanted == "Different" and state != "DIFFERENT":
                continue
            if wanted == "Unknown" and state != "UNKNOWN":
                continue
            filtered.append(game)
        self.filtered_games = filtered

        self.game_list.clear()
        for game in filtered:
            state, detail = self._game_status(game)
            item = QListWidgetItem(
                f"{STATUS_SYMBOLS[state]} {game.name}\n"
                f"{platform_label(game.source_platform)} • {human_size(game.size)} • {detail}"
            )
            item.setData(Qt.ItemDataRole.UserRole, game)
            self.game_list.addItem(item)

        self.apply_view_mode()
        target_label = "PlayStation Vita" if self.target_key == "vita" else "Nintendo DS"
        self.source_label.setText(
            f"{root} • {len(filtered)} games shown • {target_label} target"
        )
        self.update_summary()

    def _game_status(self, game: Game) -> tuple[str, str]:
        if self.target_key != "vita":
            return "UNKNOWN", "Target status managed in Device"
        try:
            return game_status(self.vita, game, self.mappings)
        except Exception:
            return "UNKNOWN", "Unable to inspect destination"

    def apply_view_mode(self) -> None:
        if self.view_mode.currentText() == "Tiles":
            self.game_list.setViewMode(QListWidget.ViewMode.IconMode)
            self.game_list.setResizeMode(QListWidget.ResizeMode.Adjust)
            self.game_list.setMovement(QListWidget.Movement.Static)
            self.game_list.setGridSize(QSize(250, 90))
            self.game_list.setIconSize(QSize(32, 32))
        else:
            self.game_list.setViewMode(QListWidget.ViewMode.ListMode)
            self.game_list.setResizeMode(QListWidget.ResizeMode.Fixed)
            self.game_list.setMovement(QListWidget.Movement.Static)

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
        self.copy_button.setVisible(is_vita)
        self.copy_button.setEnabled(
            is_vita and self.vita is not None and bool(selected) and not worker_running
        )
        self.selection_label.setText(f"{len(selected)} selected • {human_size(total)}")
        if len(selected) != 1:
            if selected and is_vita:
                if self.vita is None:
                    self.destination_label.setText("Connect the Vita to copy the selected games.")
                else:
                    self.destination_label.setText(f"Ready to copy {len(selected)} games to the Vita.")
            else:
                self.destination_label.setText(
                    "Multiple games selected." if selected else "Select a game to see its destination."
                )
            return
        if not is_vita:
            self.destination_label.setText("Deployment destination is selected from the Device workflow.")
            return
        if self.vita is None:
            self.destination_label.setText("Connect the Vita to copy this game.")
            return
        label, path, _mode = destination_for_game(self.vita, selected[0], self.mappings)
        self.destination_label.setText(f"{label} • {path}")

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
        if self.vita is None:
            QMessageBox.warning(
                self,
                "Vita not connected",
                "Connect the Vita in VitaShell USB mode first.",
            )
            return

        selected = self.selected_games()
        if not selected:
            QMessageBox.information(self, "Nothing selected", "Select one or more games first.")
            return

        jobs = []
        review: list[str] = []
        replacements: list[str] = []
        for game in selected:
            state, _detail = self._game_status(game)
            if state == "INSTALLED":
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
        self.status_filter.setEnabled(not running and self.target_key == "vita")
        self.view_mode.setEnabled(not running)
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
        self.refresh_library()
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
