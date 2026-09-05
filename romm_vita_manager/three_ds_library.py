from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSortFilterProxyModel, QTimer, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .design_tokens import DARK, brand_for_platform
from .library_sources import get_library_source
from .mappings import normalize_platform_slug, platform_label
from .models import Game
from .preferences import get_device_preference
from .romm import scan_games
from .romm_library_cache import load_cached_page, save_cached_page
from .romm_remote import RomMRemoteGame
from .romm_remote_worker import RomMLibraryWorker
from .three_ds_filesystem_deploy import ThreeDSFilesystemDeployDialog
from .three_ds_manager import RomMArtworkWorker
from .three_ds_targets import available_targets, default_destination, preferred_target_key
from .ui_components import AccentButton, SurfaceCard


LibraryGame = RomMRemoteGame | Game
PACKAGE_GENERATION_TARGETS = frozenset({"native_gba", "vc_cia"})


def _human_size(value: int) -> str:
    n = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{value} B"


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


def _local_targets(game: Game):
    targets = [
        target
        for target in available_targets(_platform_slug(game))
        if target.key not in PACKAGE_GENERATION_TARGETS
    ]
    if _platform_slug(game) == "3ds" and game.path.suffix.casefold() != ".cia":
        targets = [target for target in targets if target.key != "native_3ds_cia"]
    return tuple(targets)


def _targets_for_game(game: LibraryGame):
    return (
        available_targets(_platform_slug(game))
        if isinstance(game, RomMRemoteGame)
        else _local_targets(game)
    )


class RomMGameListModel(QAbstractListModel):
    """Compact Qt model shared by RomM-backed and local 3DS library items."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.games: list[LibraryGame] = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.games)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.games)):
            return None
        game = self.games[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return f"{game.name}\n{_platform_name(game)}  •  {_human_size(game.size)}"
        if role == Qt.ItemDataRole.UserRole:
            return game
        if role == Qt.ItemDataRole.ToolTipRole:
            source = _filename(game)
            if isinstance(game, Game):
                source = str(game.path)
            return f"{game.name}\n{_platform_name(game)} • {source}"
        return None

    def clear_games(self) -> None:
        self.beginResetModel()
        self.games.clear()
        self.endResetModel()

    def set_games(self, games: list[LibraryGame]) -> None:
        self.beginResetModel()
        self.games = list(games)
        self.endResetModel()

    def add_games(self, games: list[LibraryGame]) -> None:
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
        return isinstance(index.data(Qt.ItemDataRole.UserRole), (RomMRemoteGame, Game))


class ThreeDSLibraryWidget(QWidget):
    """3DS master/detail library for either a RomM server or local ROM directory."""

    PAGE_SIZE = 24
    SCROLL_THRESHOLD = 15

    def __init__(self, config: dict, open_manager_callback, parent=None):
        super().__init__(parent)
        self.config = config
        self.open_manager_callback = open_manager_callback
        self.library_worker: RomMLibraryWorker | None = None
        self.artwork_worker: RomMArtworkWorker | None = None
        self.games: list[LibraryGame] = []
        self._local_games: list[Game] = []
        self._loading = False
        self._remote_offset = 0
        self._platform_cursor = 0
        self._generation = 0
        self._cache_displayed = False
        self._end_reached = False
        self._artwork_rom_id: int | None = None
        self._active_artwork_rom_id: int | None = None
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(180)
        self._filter_timer.timeout.connect(self._reload_for_filter)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search games")
        self.search.setClearButtonEnabled(True)
        self.platforms = QComboBox()
        self.platforms.addItem("All compatible platforms", "")
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_library)
        self.search.textChanged.connect(self._schedule_filter)
        self.platforms.currentIndexChanged.connect(self._schedule_filter)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)
        controls.addWidget(self.search, 1)
        controls.addWidget(self.platforms)
        controls.addWidget(self.refresh_button)

        self.status = QLabel("Ready")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            f"color:{DARK.text_secondary};font-size:10px;padding:0 2px;"
        )

        self.list_model = RomMGameListModel(self)
        self.list_proxy = RomMGameFilterProxy(self)
        self.list_proxy.setSourceModel(self.list_model)
        self.game_list = QListView()
        self.game_list.setModel(self.list_proxy)
        self.game_list.setUniformItemSizes(True)
        self.game_list.setSpacing(2)
        self.game_list.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.game_list.selectionModel().currentChanged.connect(self._selected_changed)
        self.game_list.verticalScrollBar().valueChanged.connect(self._scroll_changed)

        library_card = SurfaceCard()
        library_card.content.setContentsMargins(10, 10, 10, 10)
        library_card.content.addWidget(self.game_list, 1)

        inspector = SurfaceCard()
        inspector.setMinimumWidth(310)
        inspector.setMaximumWidth(390)
        inspector_heading = QLabel("Selected game")
        inspector_heading.setStyleSheet(
            f"color:{DARK.text_secondary};font-size:10px;font-weight:700;letter-spacing:1px;"
        )
        inspector.content.addWidget(inspector_heading)

        self.artwork = QLabel("Select a game")
        self.artwork.setObjectName("gameArtwork")
        self.artwork.setFixedSize(230, 230)
        self.artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artwork.setStyleSheet(
            f"background:#151517;border:1px solid {DARK.separator};"
            f"border-radius:12px;color:{DARK.text_tertiary};"
        )
        inspector.content.addWidget(self.artwork, 0, Qt.AlignmentFlag.AlignHCenter)

        self.details = QLabel(
            "Choose a title to see its compatible Nintendo 3DS deployment routes."
        )
        self.details.setObjectName("gameDetails")
        self.details.setWordWrap(True)
        self.details.setStyleSheet(f"color:{DARK.text_secondary};line-height:1.2;")
        inspector.content.addWidget(self.details)

        target_label = QLabel("Deployment target")
        target_label.setStyleSheet(
            f"color:{DARK.text_tertiary};font-size:10px;font-weight:600;"
        )
        inspector.content.addWidget(target_label)
        self.target_combo = QComboBox()
        self.target_combo.currentIndexChanged.connect(self._target_changed)
        inspector.content.addWidget(self.target_combo)

        destination_label = QLabel("Destination")
        destination_label.setStyleSheet(
            f"color:{DARK.text_tertiary};font-size:10px;font-weight:600;"
        )
        inspector.content.addWidget(destination_label)
        self.destination = QLineEdit()
        self.destination.setReadOnly(True)
        self.destination.setPlaceholderText("Select a compatible target")
        inspector.content.addWidget(self.destination)

        self.deploy_button = AccentButton(
            "Deploy to Nintendo 3DS",
            brand_for_platform("3ds").accent,
        )
        self.deploy_button.setEnabled(False)
        self.deploy_button.clicked.connect(self._open_manager)
        inspector.content.addWidget(self.deploy_button)
        inspector.content.addStretch(1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(library_card)
        splitter.addWidget(inspector)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([820, 340])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addLayout(controls)
        layout.addWidget(self.status)
        layout.addWidget(splitter, 1)

        self.refresh_library()

    def _source_mode(self) -> str:
        return get_library_source(self.config).mode

    def _source(self) -> tuple[str, str] | None:
        source = get_library_source(self.config)
        if source.mode != "romm_api":
            return None
        url = source.romm_url.strip()
        token = source.api_token.strip()
        return (url, token) if url and token else None

    def refresh_library(self) -> None:
        self._filter_timer.stop()
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self._generation += 1
        self._clear_results(clear_platforms=True)
        if self._source_mode() == "local":
            self._load_local_library()
        else:
            self._start_page(reset=True, prefer_cache=True)

    def _clear_results(self, *, clear_platforms: bool = False) -> None:
        self._loading = False
        self._cache_displayed = False
        self._end_reached = False
        self.games = []
        self._local_games = []
        self._remote_offset = 0
        self._platform_cursor = 0
        self.list_model.clear_games()
        if clear_platforms:
            self.platforms.blockSignals(True)
            self.platforms.clear()
            self.platforms.addItem("All compatible platforms", "")
            self.platforms.blockSignals(False)
        self._clear_details()

    def _load_local_library(self) -> None:
        source = get_library_source(self.config)
        root = Path(source.local_root).expanduser()
        if not root.is_dir():
            self.status.setText(
                "The configured local library is unavailable. Reconnect it or choose another source in Settings."
            )
            return

        compatible = [game for game in scan_games(root) if _local_targets(game)]
        self._local_games = compatible
        slugs = sorted({_platform_slug(game) for game in compatible})
        self.platforms.blockSignals(True)
        self.platforms.clear()
        self.platforms.addItem("All compatible platforms", "")
        for slug in slugs:
            self.platforms.addItem(platform_label(slug), slug)
        self.platforms.blockSignals(False)
        self._end_reached = True
        self._apply_local_filters()
        if compatible:
            self.status.setText(
                f"{len(compatible):,} compatible games loaded from local library."
            )
        else:
            self.status.setText(
                "No Nintendo 3DS-compatible games were found in the configured local library."
            )

    def _schedule_filter(self) -> None:
        self._filter_timer.start()

    def _reload_for_filter(self) -> None:
        if self._source_mode() == "local":
            self._apply_local_filters()
            return
        if self.library_worker and self.library_worker.isRunning():
            self._filter_timer.start()
            return
        self._generation += 1
        self._clear_results(clear_platforms=False)
        self._start_page(reset=True, prefer_cache=True)

    def _apply_local_filters(self) -> None:
        query = self.search.text().strip().casefold()
        slug = str(self.platforms.currentData() or "").lower()
        filtered = [
            game
            for game in self._local_games
            if (not query or query in game.name.casefold())
            and (not slug or _platform_slug(game) == slug)
        ]
        self.games = list(filtered)
        self.list_model.set_games(self.games)
        self._clear_details()
        if self._local_games:
            self.status.setText(
                f"{len(filtered):,} of {len(self._local_games):,} compatible local games shown."
            )

    def _cached_query(self) -> tuple[str, str | None]:
        return self.search.text().strip(), str(self.platforms.currentData() or "") or None

    def _show_cached_page(self, instance_url: str) -> bool:
        search_term, platform_slug = self._cached_query()
        cached = load_cached_page(instance_url, search_term, platform_slug)
        if not cached:
            return False
        self.games = list(cached)
        self._remote_offset = len(cached) if platform_slug else 0
        self._platform_cursor = 0
        self._cache_displayed = True
        self.list_model.add_games(list(cached))
        self.status.setText(
            f"Showing {len(cached):,} cached results while RomM refreshes…"
        )
        return True

    def _start_page(self, *, reset: bool = False, prefer_cache: bool = False) -> None:
        source = self._source()
        if source is None:
            self.status.setText(
                "RomM is not configured. Choose a valid library source in Settings."
            )
            return
        if self.library_worker and self.library_worker.isRunning():
            return
        if self._end_reached and not reset:
            return

        url, token = source
        search_term = self.search.text().strip()
        platform_slug = str(self.platforms.currentData() or "") or None
        if reset:
            self._remote_offset = 0
            self._platform_cursor = 0
            self.list_model.clear_games()
            self.games = []
            self._cache_displayed = False
            self._end_reached = False
            if prefer_cache:
                self._show_cached_page(url)

        self._loading = True
        self.refresh_button.setEnabled(False)
        if self._cache_displayed:
            text = "Showing cached results while refreshing RomM…"
        elif search_term:
            text = f"Searching RomM for ‘{search_term}’…"
        elif platform_slug:
            text = f"Loading {self.platforms.currentText()} from RomM…"
        else:
            text = "Loading compatible games from RomM…"
        self.status.setText(text)

        request_offset = 0 if self._cache_displayed else (
            self._remote_offset if platform_slug else self._platform_cursor
        )
        worker = RomMLibraryWorker(
            url,
            token,
            page_size=self.PAGE_SIZE,
            offset=request_offset,
            search_term=search_term,
            platform_slug=platform_slug,
        )
        generation = self._generation
        worker.loaded.connect(
            lambda batch, g=generation, w=worker: self._loaded_batch(batch, g, w)
        )
        worker.platforms_loaded.connect(
            lambda platforms, g=generation: self._platforms_loaded(platforms, g)
        )
        worker.failed.connect(lambda message, g=generation: self._failed(message, g))
        worker.finished.connect(lambda g=generation: self._finished(g))
        self.library_worker = worker
        worker.start()

    def _platforms_loaded(self, platforms, generation: int) -> None:
        if generation != self._generation:
            return
        existing = {self.platforms.itemText(index) for index in range(self.platforms.count())}
        additions = [
            item
            for item in platforms
            if isinstance(item, dict)
            and item.get("name")
            and str(item.get("name")) not in existing
        ]
        if not additions:
            return
        current_slug = str(self.platforms.currentData() or "")
        self.platforms.blockSignals(True)
        for item in sorted(additions, key=lambda x: str(x.get("name")).casefold()):
            self.platforms.addItem(
                str(item["name"]), str(item.get("slug") or "").lower()
            )
        index = self.platforms.findData(current_slug)
        self.platforms.setCurrentIndex(index if index >= 0 else 0)
        self.platforms.blockSignals(False)

    def _loaded_batch(self, batch, generation: int, worker: RomMLibraryWorker) -> None:
        if generation != self._generation:
            return
        batch = list(batch)
        search_term, platform_slug = self._cached_query()
        replacing_cache = self._cache_displayed
        first_page = (
            self._remote_offset == 0 if platform_slug else self._platform_cursor == 0
        )

        if replacing_cache:
            self.list_model.clear_games()
            self.games = []
            self._remote_offset = 0
            self._platform_cursor = 0
            self._cache_displayed = False
            first_page = True

        if not batch:
            self._loading = False
            self.refresh_button.setEnabled(True)
            if replacing_cache or not self.games:
                self.status.setText(
                    "No matching games were found in RomM. Change the search or platform filter."
                )
                self._clear_details()
            if platform_slug or self._platform_cursor >= worker.platforms_total:
                self._end_reached = True
            return

        self.games.extend(batch)
        self.list_model.add_games(batch)
        if platform_slug:
            self._remote_offset += len(batch)
            self._end_reached = len(batch) < self.PAGE_SIZE
        else:
            self._platform_cursor += worker.platforms_consumed
            self._end_reached = self._platform_cursor >= worker.platforms_total

        self._loading = False
        self.refresh_button.setEnabled(True)
        if first_page:
            source = self._source()
            if source is not None:
                save_cached_page(source[0], batch, search_term, platform_slug)

        scope = self.platforms.currentText() if platform_slug else "compatible platforms"
        suffix = " End of library." if self._end_reached else " Scroll for more."
        self.status.setText(f"{len(self.games):,} games loaded from {scope}.{suffix}")

    def _scroll_changed(self, value: int) -> None:
        if self._source_mode() == "local":
            return
        bar = self.game_list.verticalScrollBar()
        if bar.maximum() - value > self.SCROLL_THRESHOLD:
            return
        if self._loading or not self.games or self._end_reached:
            return
        self._start_page()

    def _failed(self, message: str, generation: int) -> None:
        if generation != self._generation:
            return
        self._loading = False
        self.refresh_button.setEnabled(True)
        self.status.setText(
            f"Showing {len(self.games):,} cached/loaded games. RomM refresh failed: {message}"
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
            self.status.setText("No matching games were found in RomM.")
        if self._filter_timer.isActive():
            self._filter_timer.stop()
            QTimer.singleShot(0, self._reload_for_filter)

    def _selected_game(self) -> LibraryGame | None:
        index = self.game_list.currentIndex()
        value = index.data(Qt.ItemDataRole.UserRole) if index.isValid() else None
        return value if isinstance(value, (RomMRemoteGame, Game)) else None

    def _selected_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        game = current.data(Qt.ItemDataRole.UserRole) if current.isValid() else None
        if not isinstance(game, (RomMRemoteGame, Game)):
            self._clear_details()
            return

        targets = _targets_for_game(game)
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        for target in targets:
            self.target_combo.addItem(target.label, target.key)
        preference = get_device_preference(self.config, "3ds")
        preferred = preferred_target_key(_platform_slug(game), preference)
        preferred_index = self.target_combo.findData(preferred) if preferred else -1
        if preferred_index >= 0:
            self.target_combo.setCurrentIndex(preferred_index)
        self.target_combo.blockSignals(False)
        self.details.setText(
            f"{game.name}\n{_platform_name(game)}  •  {_human_size(game.size)}"
        )
        self.deploy_button.setEnabled(bool(targets))
        self._load_artwork(game)
        self._target_changed()

    def _target_changed(self) -> None:
        game = self._selected_game()
        if game is None or self.target_combo.count() == 0:
            self.destination.clear()
            self.deploy_button.setEnabled(False)
            return
        target_key = str(self.target_combo.currentData())
        self.destination.setText(
            default_destination(target_key, _platform_slug(game), _filename(game))
        )
        target = next(
            (t for t in _targets_for_game(game) if t.key == target_key),
            None,
        )
        if target:
            source_note = "Local file" if isinstance(game, Game) else "RomM library"
            self.details.setText(
                f"{game.name}\n{_platform_name(game)}  •  {_human_size(game.size)}"
                f"\n\n{target.description}\n\nSource: {source_note}"
            )
        self.deploy_button.setEnabled(target is not None)
        self.deploy_button.setText(
            "Open package workflow"
            if target_key in PACKAGE_GENERATION_TARGETS
            else "Deploy to Nintendo 3DS"
        )

    def _load_artwork(self, game: LibraryGame) -> None:
        self.artwork.clear()
        if isinstance(game, Game):
            self._artwork_rom_id = None
            self._active_artwork_rom_id = None
            self.artwork.setText("Local file")
            return

        self._artwork_rom_id = game.rom_id
        self.artwork.setText(
            "Loading artwork…" if game.cover_url else "No artwork available"
        )
        if not game.cover_url:
            return
        if self.artwork_worker and self.artwork_worker.isRunning():
            return

        source = self._source()
        if source is None:
            self.artwork.setText("RomM artwork unavailable")
            return
        instance_url, token = source
        requested_rom_id = game.rom_id
        worker = RomMArtworkWorker(game.cover_url, token, instance_url)
        worker.loaded.connect(
            lambda data, rid=requested_rom_id: self._artwork_loaded(data, rid)
        )
        worker.failed.connect(
            lambda msg, rid=requested_rom_id: self._artwork_failed(msg, rid)
        )
        worker.finished.connect(self._artwork_finished)
        self._active_artwork_rom_id = requested_rom_id
        self.artwork_worker = worker
        worker.start()

    def _artwork_loaded(self, data: bytes, rom_id: int) -> None:
        if rom_id != self._artwork_rom_id:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            self.artwork.setText("Artwork unavailable")
            return
        self.artwork.setPixmap(
            pixmap.scaled(
                220,
                220,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _artwork_failed(self, message: str, rom_id: int) -> None:
        if rom_id == self._artwork_rom_id:
            self.artwork.setText(f"Artwork unavailable\n{message}")

    def _artwork_finished(self) -> None:
        finished_rom_id = self._active_artwork_rom_id
        self._active_artwork_rom_id = None
        self.artwork_worker = None
        current = self._selected_game()
        if (
            isinstance(current, RomMRemoteGame)
            and current.cover_url
            and current.rom_id == self._artwork_rom_id
            and current.rom_id != finished_rom_id
        ):
            QTimer.singleShot(0, lambda game=current: self._load_artwork(game))

    def _clear_details(self) -> None:
        self._artwork_rom_id = None
        self.artwork.clear()
        self.artwork.setText("Select a game")
        self.details.setText(
            "Choose a title to see its compatible Nintendo 3DS deployment routes."
        )
        self.destination.clear()
        self.target_combo.clear()
        self.deploy_button.setText("Deploy to Nintendo 3DS")
        self.deploy_button.setEnabled(False)

    def _open_manager(self) -> None:
        game = self._selected_game()
        target_key = str(self.target_combo.currentData() or "")
        if game is None or not target_key:
            return
        if target_key in PACKAGE_GENERATION_TARGETS:
            self.open_manager_callback(game, target_key)
            return
        ThreeDSFilesystemDeployDialog(self.config, game, target_key, self).exec()

    def closeEvent(self, event) -> None:
        self._filter_timer.stop()
        for worker in (self.library_worker, self.artwork_worker):
            if worker is not None and worker.isRunning():
                worker.requestInterruption()
                worker.wait()
        super().closeEvent(event)
