from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .romm_remote import RomMRemoteGame
from .romm_remote_worker import RomMLibraryWorker
from .three_ds_targets import available_targets, default_destination
from .three_ds_manager import RomMArtworkWorker


class ThreeDSLibraryWidget(QWidget):
    """Responsive, incremental RomM browser for content deployable to a 3DS."""

    def __init__(self, config: dict, open_manager_callback, parent=None):
        super().__init__(parent)
        self.config = config
        self.open_manager_callback = open_manager_callback
        self.library_worker: RomMLibraryWorker | None = None
        self.artwork_worker: RomMArtworkWorker | None = None
        self.games: list[RomMRemoteGame] = []
        self._loading = False
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(120)
        self._filter_timer.timeout.connect(self._apply_filter)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search compatible games…")
        self.platforms = QComboBox()
        self.platforms.addItem("All platforms")
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_library)
        self.search.textChanged.connect(self._schedule_filter)
        self.platforms.currentIndexChanged.connect(self._apply_filter)

        self.game_list = QListWidget()
        self.game_list.itemSelectionChanged.connect(self._selected_changed)

        self.artwork = QLabel("Select a game")
        self.artwork.setFixedSize(220, 220)
        self.artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.details = QLabel("RomM games compatible with the configured 3DS deployment targets will appear here.")
        self.details.setWordWrap(True)

        self.target_combo = QComboBox()
        self.target_combo.currentIndexChanged.connect(self._target_changed)
        self.destination = QLineEdit()
        self.destination.setReadOnly(True)
        self.deploy_button = QPushButton("Deploy Selected Game")
        self.deploy_button.clicked.connect(self._open_manager)

        controls = QHBoxLayout()
        controls.addWidget(self.search, 1)
        controls.addWidget(self.platforms)
        controls.addWidget(self.refresh_button)

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Target:"))
        target_row.addWidget(self.target_combo, 1)
        target_row.addWidget(QLabel("Destination:"))
        target_row.addWidget(self.destination, 2)
        target_row.addWidget(self.deploy_button)

        details_row = QHBoxLayout()
        details_row.addWidget(self.artwork)
        details_row.addWidget(self.details, 1)

        self.status = QLabel("Ready.")
        self.status.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.status)
        layout.addWidget(self.game_list, 1)
        layout.addLayout(details_row)
        layout.addLayout(target_row)

        self.refresh_library()

    def _schedule_filter(self) -> None:
        self._filter_timer.start()

    def refresh_library(self) -> None:
        if self.library_worker and self.library_worker.isRunning():
            return
        source = self.config.get("library_source", {})
        mode = str(source.get("mode", "local")).lower() if isinstance(source, dict) else "local"
        if mode != "romm_api":
            self.games = []
            self.game_list.clear()
            self.status.setText("Set the library source to RomM Server in Settings to browse the remote library.")
            return
        url = str(source.get("romm_url", "")).strip()
        token = str(source.get("api_token", "")).strip()
        if not url or not token:
            self.status.setText("RomM Server is selected but the URL or Client API Token is missing.")
            return

        self.games = []
        self.game_list.clear()
        self.platforms.blockSignals(True)
        self.platforms.clear()
        self.platforms.addItem("All platforms")
        self.platforms.blockSignals(False)
        self._loading = True
        self.refresh_button.setEnabled(False)
        self.status.setText(f"Loading compatible RomM library from {url}…")
        self.library_worker = RomMLibraryWorker(url, token)
        self.library_worker.loaded.connect(self._loaded_batch)
        self.library_worker.failed.connect(self._failed)
        self.library_worker.finished.connect(self._finished)
        self.library_worker.start()

    def _loaded_batch(self, batch) -> None:
        batch = list(batch)
        if not batch:
            return
        self.games.extend(batch)

        existing_platforms = {
            self.platforms.itemText(index)
            for index in range(self.platforms.count())
        }
        new_platforms = sorted(
            {game.platform for game in batch if game.platform not in existing_platforms},
            key=str.lower,
        )
        if new_platforms:
            current = self.platforms.currentText()
            self.platforms.blockSignals(True)
            self.platforms.addItems(new_platforms)
            self.platforms.setCurrentText(current)
            self.platforms.blockSignals(False)

        query = self.search.text().strip()
        platform = self.platforms.currentText()
        if not query and platform == "All platforms":
            self.game_list.setUpdatesEnabled(False)
            for game in batch:
                self._add_game_item(game)
            self.game_list.setUpdatesEnabled(True)
        else:
            self._apply_filter()

        self.status.setText(
            f"Loading RomM library… {len(self.games):,} compatible files loaded."
        )

    def _add_game_item(self, game: RomMRemoteGame) -> None:
        item = QListWidgetItem(f"{game.name} • {game.platform} • {game.size:,} bytes")
        item.setData(Qt.ItemDataRole.UserRole, game)
        self.game_list.addItem(item)

    def _failed(self, message: str) -> None:
        self._loading = False
        self.refresh_button.setEnabled(True)
        if self.games:
            self.status.setText(
                f"RomM library load stopped after {len(self.games):,} files: {message}"
            )
        else:
            self.status.setText(f"RomM library unavailable: {message}")
            self.game_list.clear()

    def _finished(self) -> None:
        self.library_worker = None
        self._loading = False
        self.refresh_button.setEnabled(True)
        self.status.setText(f"RomM library ready: {len(self.games):,} compatible files.")

    def _apply_filter(self) -> None:
        query = self.search.text().strip().lower()
        platform = self.platforms.currentText()
        selected = self._selected_game()
        visible = [
            game for game in self.games
            if (not query or query in game.name.lower() or query in game.filename.lower())
            and (platform == "All platforms" or game.platform == platform)
        ]
        self.game_list.setUpdatesEnabled(False)
        self.game_list.clear()
        for game in visible:
            self._add_game_item(game)
        self.game_list.setUpdatesEnabled(True)
        if visible:
            if selected is not None:
                for row, game in enumerate(visible):
                    if game.rom_id == selected.rom_id:
                        self.game_list.setCurrentRow(row)
                        break
                else:
                    self.game_list.setCurrentRow(0)
            else:
                self.game_list.setCurrentRow(0)
        else:
            self._clear_details()

    def _selected_game(self) -> RomMRemoteGame | None:
        item = self.game_list.currentItem()
        value = item.data(Qt.ItemDataRole.UserRole) if item else None
        return value if isinstance(value, RomMRemoteGame) else None

    def _selected_changed(self) -> None:
        game = self._selected_game()
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        if game is None:
            self._clear_details()
            self.target_combo.blockSignals(False)
            self.deploy_button.setEnabled(False)
            return
        targets = available_targets(game.platform_slug)
        for target in targets:
            self.target_combo.addItem(target.label, target.key)
        self.target_combo.blockSignals(False)
        self.details.setText(
            f"{game.name}\n{game.platform} ({game.platform_slug}) • {game.size:,} bytes\n"
            "Artwork: RomM metadata"
        )
        self.deploy_button.setEnabled(bool(targets))
        self._load_artwork(game)
        self._target_changed()

    def _target_changed(self) -> None:
        game = self._selected_game()
        if game is None or self.target_combo.count() == 0:
            self.destination.clear()
            return
        target_key = str(self.target_combo.currentData())
        self.destination.setText(default_destination(target_key, game.platform_slug, game.filename))
        target = next((t for t in available_targets(game.platform_slug) if t.key == target_key), None)
        if target:
            self.details.setText(
                f"{game.name}\n{game.platform} ({game.platform_slug}) • {game.size:,} bytes\n\n{target.description}"
            )

    def _load_artwork(self, game: RomMRemoteGame) -> None:
        if self.artwork_worker and self.artwork_worker.isRunning():
            return
        self.artwork.clear()
        self.artwork.setText("Loading artwork…" if game.cover_url else "No artwork in RomM")
        if not game.cover_url:
            return
        source = self.config.get("library_source", {})
        token = str(source.get("api_token", "")) if isinstance(source, dict) else ""
        self.artwork_worker = RomMArtworkWorker(game.cover_url, token)
        self.artwork_worker.loaded.connect(self._artwork_loaded)
        self.artwork_worker.failed.connect(lambda msg: self.artwork.setText(f"Artwork unavailable\n{msg}"))
        self.artwork_worker.finished.connect(lambda: setattr(self, "artwork_worker", None))
        self.artwork_worker.start()

    def _artwork_loaded(self, data: bytes) -> None:
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            self.artwork.setText("Artwork unavailable")
            return
        self.artwork.setPixmap(
            pixmap.scaled(220, 220, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )

    def _clear_details(self) -> None:
        self.artwork.clear()
        self.artwork.setText("Select a game")
        self.details.setText("RomM games compatible with the configured 3DS deployment targets will appear here.")
        self.destination.clear()
        self.target_combo.clear()
        self.deploy_button.setEnabled(False)

    def _open_manager(self) -> None:
        game = self._selected_game()
        target_key = str(self.target_combo.currentData() or "")
        if game is not None and target_key:
            self.open_manager_callback(game, target_key)
