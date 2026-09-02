from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSortFilterProxyModel, QTimer, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QListView, QPushButton, QVBoxLayout, QWidget

from .romm_library_cache import load_cached_page, save_cached_page
from .romm_remote import RomMRemoteGame
from .romm_remote_worker import RomMLibraryWorker
from .three_ds_targets import available_targets, default_destination
from .three_ds_manager import RomMArtworkWorker


class RomMGameListModel(QAbstractListModel):
    """Compact Qt model for large RomM libraries."""

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
        self.beginInsertRows(QModelIndex(), start, start + len(games) - 1)
        self.games.extend(games)
        self.endInsertRows()


class RomMGameFilterProxy(QSortFilterProxyModel):
    """Pass-through proxy retained for compatibility with existing UI code."""

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        index = self.sourceModel().index(source_row, 0, source_parent)
        return isinstance(index.data(Qt.ItemDataRole.UserRole), RomMRemoteGame)


class ThreeDSLibraryWidget(QWidget):
    """Lazy, server-searched RomM browser with an instant local first-page cache."""

    PAGE_SIZE = 24
    SCROLL_THRESHOLD = 15

    def __init__(self, config: dict, open_manager_callback, parent=None):
        super().__init__(parent)
        self.config = config
        self.open_manager_callback = open_manager_callback
        self.library_worker: RomMLibraryWorker | None = None
        self.artwork_worker: RomMArtworkWorker | None = None
        self.games: list[RomMRemoteGame] = []
        self._loading = False
        self._offset = 0
        self._generation = 0
        self._cache_displayed = False
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(180)
        self._filter_timer.timeout.connect(self._reload_for_filter)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search compatible games…")
        self.platforms = QComboBox()
        self.platforms.addItem("All platforms", "")
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_library)
        self.search.textChanged.connect(self._schedule_filter)
        self.platforms.currentIndexChanged.connect(self._schedule_filter)

        self.list_model = RomMGameListModel(self)
        self.list_proxy = RomMGameFilterProxy(self)
        self.list_proxy.setSourceModel(self.list_model)
        self.game_list = QListView()
        self.game_list.setModel(self.list_proxy)
        self.game_list.setUniformItemSizes(True)
        self.game_list.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.game_list.selectionModel().currentChanged.connect(self._selected_changed)
        self.game_list.verticalScrollBar().valueChanged.connect(self._scroll_changed)

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

    def _source(self) -> tuple[str, str] | None:
        source = self.config.get("library_source", {})
        mode = str(source.get("mode", "local")).lower() if isinstance(source, dict) else "local"
        if mode != "romm_api":
            return None
        url = str(source.get("romm_url", "")).strip()
        token = str(source.get("api_token", "")).strip()
        return (url, token) if url and token else None

    def refresh_library(self) -> None:
        self._filter_timer.stop()
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self._generation += 1
        self._clear_results(clear_platforms=True)
        self._start_page(reset=True, prefer_cache=True)

    def _clear_results(self, *, clear_platforms: bool = False) -> None:
        self._loading = False
        self._cache_displayed = False
        self.games = []
        self._offset = 0
        self.list_model.clear_games()
        if clear_platforms:
            self.platforms.blockSignals(True)
            self.platforms.clear()
            self.platforms.addItem("All platforms", "")
            self.platforms.blockSignals(False)
        self._clear_details()

    def _schedule_filter(self) -> None:
        self._filter_timer.start()

    def _reload_for_filter(self) -> None:
        if self.library_worker and self.library_worker.isRunning():
            self._filter_timer.start()
            return
        self._generation += 1
        self._clear_results(clear_platforms=False)
        self._start_page(reset=True, prefer_cache=True)

    def _cached_query(self) -> tuple[str, str | None]:
        return self.search.text().strip(), str(self.platforms.currentData() or "") or None

    def _show_cached_page(self, instance_url: str) -> bool:
        search_term, platform_slug = self._cached_query()
        cached = load_cached_page(instance_url, search_term, platform_slug)
        if not cached:
            return False
        self.games = list(cached)
        self._offset = len(cached)
        self._cache_displayed = True
        self.list_model.add_games(cached)
        self.status.setText(f"Showing {len(cached):,} cached results. Refreshing RomM…")
        return True

    def _start_page(self, *, reset: bool = False, prefer_cache: bool = False) -> None:
        source = self._source()
        if source is None:
            self.status.setText("Set the library source to RomM Server in Settings to browse the remote library.")
            return
        if self.library_worker and self.library_worker.isRunning():
            return

        url, token = source
        search_term = self.search.text().strip()
        platform_slug = str(self.platforms.currentData() or "") or None
        if reset:
            self._offset = 0
            self.list_model.clear_games()
            self.games = []
            self._cache_displayed = False
            if prefer_cache:
                self._show_cached_page(url)

        self._loading = True
        self.refresh_button.setEnabled(False)
        scope = f" for ‘{search_term}’" if search_term else (f" for {self.platforms.currentText()}" if platform_slug else "")
        self.status.setText(
            f"Showing cached results{scope}. Refreshing RomM…"
            if self._cache_displayed
            else f"Loading RomM library{scope}…"
        )

        request_offset = 0 if self._cache_displayed else self._offset
        worker = RomMLibraryWorker(
            url,
            token,
            page_size=self.PAGE_SIZE,
            offset=request_offset,
            search_term=search_term,
            platform_slug=platform_slug,
        )
        generation = self._generation
        worker.loaded.connect(lambda batch, g=generation: self._loaded_batch(batch, g))
        worker.platforms_loaded.connect(lambda platforms, g=generation: self._platforms_loaded(platforms, g))
        worker.failed.connect(lambda message, g=generation: self._failed(message, g))
        worker.finished.connect(lambda g=generation: self._finished(g))
        self.library_worker = worker
        worker.start()

    def _platforms_loaded(self, platforms, generation: int) -> None:
        if generation != self._generation:
            return
        existing = {self.platforms.itemText(index) for index in range(self.platforms.count())}
        additions = [
            item for item in platforms
            if isinstance(item, dict) and item.get("name") and str(item.get("name")) not in existing
        ]
        if not additions:
            return
        current_slug = str(self.platforms.currentData() or "")
        self.platforms.blockSignals(True)
        for item in sorted(additions, key=lambda x: str(x.get("name")).casefold()):
            self.platforms.addItem(str(item["name"]), str(item.get("slug") or "").lower())
        index = self.platforms.findData(current_slug)
        self.platforms.setCurrentIndex(index if index >= 0 else 0)
        self.platforms.blockSignals(False)

    def _loaded_batch(self, batch, generation: int) -> None:
        if generation != self._generation:
            return
        batch = list(batch)
        search_term, platform_slug = self._cached_query()
        replacing_cache = self._cache_displayed
        if replacing_cache:
            self.list_model.clear_games()
            self.games = []
            self._offset = 0
            self._cache_displayed = False
        if not batch:
            self._loading = False
            self.refresh_button.setEnabled(True)
            if replacing_cache or not self.games:
                self.status.setText("No matching games found in RomM.")
                self._clear_details()
            return
        self.games.extend(batch)
        self.list_model.add_games(batch)
        self._offset += len(batch)
        self._loading = False
        self.refresh_button.setEnabled(True)
        if replacing_cache or self._offset == len(batch):
            source = self._source()
            if source is not None:
                save_cached_page(source[0], batch, search_term, platform_slug)
        self.status.setText(f"Showing {len(self.games):,} loaded results. Scroll for more.")

    def _scroll_changed(self, value: int) -> None:
        bar = self.game_list.verticalScrollBar()
        if bar.maximum() - value > self.SCROLL_THRESHOLD:
            return
        if self._loading or not self.games:
            return
        self._start_page()

    def _failed(self, message: str, generation: int) -> None:
        if generation != self._generation:
            return
        self._loading = False
        self.refresh_button.setEnabled(True)
        self.status.setText(
            f"Showing {len(self.games):,} cached/loaded files • RomM refresh failed: {message}"
            if self.games
            else f"RomM library unavailable: {message}"
        )

    def _finished(self, generation: int) -> None:
        if generation != self._generation:
            return
        self.library_worker = None
        self._loading = False
        self.refresh_button.setEnabled(True)
        if not self.games and not self.status.text().startswith("RomM library unavailable"):
            self.status.setText("No matching games found in RomM.")
        if self._filter_timer.isActive():
            self._filter_timer.stop()
            QTimer.singleShot(0, self._reload_for_filter)

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
        self.artwork.setPixmap(pixmap.scaled(220, 220, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

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
