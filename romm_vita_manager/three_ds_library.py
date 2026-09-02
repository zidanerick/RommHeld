from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSortFilterProxyModel, QTimer, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .romm_remote import RomMRemoteGame
from .romm_remote_worker import RomMLibraryWorker
from .three_ds_targets import available_targets, default_destination
from .three_ds_manager import RomMArtworkWorker


class RomMGameListModel(QAbstractListModel):
    """Compact Qt model that can hold large RomM libraries without rebuilding widgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.games: list[RomMRemoteGame] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.games)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.games)):
            return None
        game = self.games[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return f"{game.name} • {game.platform} • {game.size:,} bytes"
        if role == Qt.ItemDataRole.UserRole:
            return game
        return None

    def clear_games(self) -> None:
        self.beginResetModel()
        self.games.clear()
        self.endResetModel()

    def add_games(self, games: list[RomMRemoteGame]) -> None:
        if not games:
            return
        start = len(self.games)
        end = start + len(games) - 1
        self.beginInsertRows(QModelIndex(), start, end)
        self.games.extend(games)
        self.endInsertRows()


class RomMGameFilterProxy(QSortFilterProxyModel):
    """Fast in-process search/filter over the loaded RomM library."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.query = ""
        self.platform = "All platforms"
        self.setDynamicSortFilter(True)

    def set_query(self, query: str) -> None:
        self.query = query.strip().casefold()
        self.invalidateFilter()

    def set_platform(self, platform: str) -> None:
        self.platform = platform
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        index = self.sourceModel().index(source_row, 0, source_parent)
        game = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(game, RomMRemoteGame):
            return False
        if self.platform != "All platforms" and game.platform != self.platform:
            return False
        if not self.query:
            return True
        return self.query in game.name.casefold() or self.query in game.filename.casefold()


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

        self.list_model = RomMGameListModel(self)
        self.list_proxy = RomMGameFilterProxy(self)
        self.list_proxy.setSourceModel(self.list_model)
        self.game_list = QListView()
        self.game_list.setModel(self.list_proxy)
        self.game_list.setUniformItemSizes(True)
        self.game_list.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.game_list.selectionModel().currentChanged.connect(self._selected_changed)

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
            self.list_model.clear_games()
            self.status.setText("Set the library source to RomM Server in Settings to browse the remote library.")
            return
        url = str(source.get("romm_url", "")).strip()
        token = str(source.get("api_token", "")).strip()
        if not url or not token:
            self.status.setText("RomM Server is selected but the URL or Client API Token is missing.")
            return

        self.games = []
        self.list_model.clear_games()
        self.platforms.blockSignals(True)
        self.platforms.clear()
        self.platforms.addItem("All platforms")
        self.platforms.blockSignals(False)
        self.list_proxy.set_platform("All platforms")
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
        self.list_model.add_games(batch)

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

        self.status.setText(
            f"Loading RomM library… {len(self.games):,} compatible files loaded."
        )

    def _failed(self, message: str) -> None:
        self._loading = False
        self.refresh_button.setEnabled(True)
        if self.games:
            self.status.setText(
                f"RomM library load stopped after {len(self.games):,} files: {message}"
            )
        else:
            self.status.setText(f"RomM library unavailable: {message}")

    def _finished(self) -> None:
        self.library_worker = None
        self._loading = False
        self.refresh_button.setEnabled(True)
        if self.games:
            self.status.setText(f"RomM library ready: {len(self.games):,} compatible files.")

    def _apply_filter(self) -> None:
        self.list_proxy.set_query(self.search.text())
        self.list_proxy.set_platform(self.platforms.currentText())
        if self.games:
            self.status.setText(
                f"{self.list_proxy.rowCount():,} matches from {len(self.games):,} loaded files"
                + (" • loading more…" if self._loading else "")
            )
        elif not self._loading:
            self._clear_details()

    def _selected_game(self) -> RomMRemoteGame | None:
        index = self.game_list.currentIndex()
        value = index.data(Qt.ItemDataRole.UserRole) if index.isValid() else None
        return value if isinstance(value, RomMRemoteGame) else None

    def _selected_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        game = current.data(Qt.ItemDataRole.UserRole) if current.isValid() else None
        if not isinstance(game, RomMRemoteGame):
            self._clear_details()
            return
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
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
