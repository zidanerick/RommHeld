from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .config import save_config
from .design_tokens import DARK, brand_for_platform
from .library_sources import get_library_source
from .romm import scan_games
from .romm_remote import RomMRemoteGame, download_artwork, download_rom
from .romm_remote_worker import RomMLibraryWorker
from .three_ds_ftp import ThreeDSFtpBackend, ThreeDSFtpSettings
from .three_ds_targets import available_targets, default_destination
from .ui_components import AccentButton, SectionHeader, StatusPill, SurfaceCard


NINTENDO_RED = brand_for_platform("3ds").accent


class ThreeDSConnectionWorker(QThread):
    succeeded = Signal()
    failed = Signal(str)

    def __init__(self, settings: ThreeDSFtpSettings):
        super().__init__()
        self.settings = settings

    def run(self) -> None:
        backend = ThreeDSFtpBackend(self.settings)
        try:
            backend.connect()
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit()
        finally:
            backend.close()


class RomMArtworkWorker(QThread):
    loaded = Signal(bytes)
    failed = Signal(str)

    def __init__(self, url: str, token: str, instance_url: str = ""):
        super().__init__()
        self.url = url
        self.token = token
        self.instance_url = instance_url

    def run(self) -> None:
        try:
            data = download_artwork(self.instance_url, self.token, self.url)
            self.loaded.emit(data)
        except Exception as exc:
            self.failed.emit(str(exc))


class ThreeDSTransferWorker(QThread):
    progress = Signal(int)
    status_changed = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        settings,
        source,
        destination,
        *,
        remote_game=None,
        romm_url="",
        romm_token="",
    ):
        super().__init__()
        self.settings = settings
        self.source = source
        self.destination = destination
        self.remote_game = remote_game
        self.romm_url = romm_url
        self.romm_token = romm_token
        self.cancel_event = threading.Event()
        self.backend: ThreeDSFtpBackend | None = None
        self._temporary_path: Path | None = None

    def cancel(self) -> None:
        self.cancel_event.set()

    def _resolve_source(self) -> Path:
        if self.remote_game is None:
            if self.source is None or not self.source.is_file():
                raise FileNotFoundError(f"Source file does not exist: {self.source}")
            return self.source
        if not self.romm_url.strip() or not self.romm_token.strip():
            raise ValueError("RomM server credentials are not configured.")
        handle = tempfile.NamedTemporaryFile(
            prefix="rommheld-3ds-",
            suffix=Path(self.remote_game.filename).suffix,
            delete=False,
        )
        handle.close()
        self._temporary_path = Path(handle.name)
        self.status_changed.emit(f"Downloading {self.remote_game.name} from RomM…")
        return download_rom(
            self.romm_url,
            self.romm_token,
            self.remote_game,
            self._temporary_path,
        )

    def run(self) -> None:
        try:
            source = self._resolve_source()
            name = self.remote_game.name if self.remote_game else source.name
            self.status_changed.emit(f"Uploading {name} to the Nintendo 3DS…")
            self.backend = ThreeDSFtpBackend(self.settings)
            self.backend.connect()
            result, _ = self.backend.upload(
                source,
                self.destination,
                cancel_event=self.cancel_event,
                progress=self.progress.emit,
            )
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if self.backend is not None:
                self.backend.close()
            if self._temporary_path is not None:
                try:
                    self._temporary_path.unlink(missing_ok=True)
                except Exception:
                    pass


class ThreeDSManagerDialog(QDialog):
    """Nintendo 3DS deployment surface for compatible local or RomM content."""

    def __init__(self, config: dict, library_root: Path | None = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.library_source = get_library_source(config)
        self.library_root = library_root.expanduser() if library_root else None
        self.connection_worker: ThreeDSConnectionWorker | None = None
        self.library_worker: RomMLibraryWorker | None = None
        self.artwork_worker: RomMArtworkWorker | None = None
        self.worker: ThreeDSTransferWorker | None = None
        self._connected = False
        self._games: list[object] = []
        self._closing_requested = False

        self.setWindowTitle("Nintendo 3DS Manager")
        self.resize(1180, 780)
        self.setMinimumSize(920, 650)

        saved = config.get("devices", {}).get("3ds", {})
        self.host_edit = QLineEdit(str(saved.get("host", "")))
        self.port_edit = QLineEdit(str(saved.get("port", 5000)))
        self.user_edit = QLineEdit(str(saved.get("username", "anonymous")))
        self.password_edit = QLineEdit(str(saved.get("password", "")))
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.root_edit = QLineEdit(str(saved.get("remote_root", "/")))

        self.connect_button = AccentButton("Connect to 3DS", NINTENDO_RED)
        self.refresh_button = QPushButton("Refresh library")
        self.connect_button.clicked.connect(self.connect_3ds)
        self.refresh_button.clicked.connect(self.refresh_library)

        self.ftp_status = StatusPill("FTP", "Not connected")
        self.library_status = StatusPill("Library", "Not loaded")
        self.endpoint_label = QLabel(self._endpoint_text())
        self.endpoint_label.setProperty("secondary", True)
        self.endpoint_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.settings_toggle = QToolButton()
        self.settings_toggle.setText("FTP connection settings")
        self.settings_toggle.setCheckable(True)
        self.settings_toggle.setChecked(not bool(self.host_edit.text().strip()))
        self.settings_toggle.setArrowType(
            Qt.ArrowType.DownArrow
            if self.settings_toggle.isChecked()
            else Qt.ArrowType.RightArrow
        )
        self.settings_toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.settings_toggle.toggled.connect(self._toggle_connection_settings)

        self.connection_settings = QFrame()
        settings_form = QFormLayout(self.connection_settings)
        settings_form.setContentsMargins(0, 4, 0, 0)
        settings_form.setHorizontalSpacing(12)
        settings_form.setVerticalSpacing(8)
        settings_form.addRow("Host", self.host_edit)
        settings_form.addRow("Port", self.port_edit)
        settings_form.addRow("Username", self.user_edit)
        settings_form.addRow("Password", self.password_edit)
        settings_form.addRow("Remote root", self.root_edit)
        self.connection_settings.setVisible(self.settings_toggle.isChecked())

        connection_card = SurfaceCard()
        connection_top = QHBoxLayout()
        connection_top.setSpacing(8)
        connection_top.addWidget(self.ftp_status)
        connection_top.addWidget(self.endpoint_label, 1)
        connection_top.addWidget(self.connect_button)
        connection_card.content.addLayout(connection_top)
        connection_card.content.addWidget(self.settings_toggle)
        connection_card.content.addWidget(self.connection_settings)

        self.source_label = QLabel("Library source: not loaded")
        self.source_label.setWordWrap(True)
        self.source_label.setProperty("secondary", True)

        self.game_list = QListWidget()
        self.game_list.setAlternatingRowColors(False)
        self.game_list.itemSelectionChanged.connect(self.game_selected)

        library_card = SurfaceCard()
        library_head = QHBoxLayout()
        library_head.addWidget(self.library_status)
        library_head.addStretch()
        library_head.addWidget(self.refresh_button)
        library_card.content.addLayout(library_head)
        library_card.content.addWidget(self.source_label)
        library_card.content.addWidget(self.game_list, 1)

        self.artwork = QLabel("No artwork")
        self.artwork.setFixedSize(220, 220)
        self.artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artwork.setObjectName("threeDSArtwork")
        self.artwork.setStyleSheet(
            f"QLabel#threeDSArtwork{{background:{DARK.surface_raised};"
            f"border:1px solid {DARK.separator};border-radius:12px;"
            f"color:{DARK.text_tertiary};padding:8px;}}"
        )

        self.details = QLabel("Select a game to see deployment options.")
        self.details.setWordWrap(True)
        self.details.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.details.setStyleSheet(f"color:{DARK.text_secondary};")

        selection_top = QHBoxLayout()
        selection_top.setSpacing(14)
        selection_top.addWidget(self.artwork)
        selection_top.addWidget(self.details, 1, Qt.AlignmentFlag.AlignTop)

        self.target_combo = QComboBox()
        self.target_combo.currentIndexChanged.connect(self.target_changed)

        self.destination_edit = QLineEdit()
        self.destination_edit.setPlaceholderText("Remote destination")

        deploy_form = QFormLayout()
        deploy_form.setContentsMargins(0, 0, 0, 0)
        deploy_form.setHorizontalSpacing(12)
        deploy_form.setVerticalSpacing(8)
        deploy_form.addRow("Deployment target", self.target_combo)
        deploy_form.addRow("Destination", self.destination_edit)

        self.send_button = AccentButton("Deploy selected game", NINTENDO_RED)
        self.cancel_button = QPushButton("Cancel transfer")
        self.cancel_button.setEnabled(False)
        self.send_button.clicked.connect(self.send_selected)
        self.cancel_button.clicked.connect(self.cancel_transfer)

        action_row = QHBoxLayout()
        action_row.addStretch()
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.send_button)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setVisible(False)

        self.status = QLabel(
            "Ready. Library access and the Nintendo 3DS FTP connection operate independently."
        )
        self.status.setWordWrap(True)
        self.status.setProperty("secondary", True)

        detail_card = SurfaceCard()
        detail_card.content.addLayout(selection_top)
        detail_card.content.addLayout(deploy_form)
        detail_card.content.addWidget(self.progress)
        detail_card.content.addWidget(self.status)
        detail_card.content.addLayout(action_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(library_card)
        splitter.addWidget(detail_card)
        splitter.setSizes([620, 460])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        header = SectionHeader(
            "Nintendo 3DS Manager",
            "Browse compatible games, choose how they should run, then deploy through the appropriate 3DS workflow.",
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(header)
        layout.addWidget(connection_card)
        layout.addWidget(splitter, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        close_row.addWidget(close)
        layout.addLayout(close_row)

        self.refresh_library()
        self._update_controls()

    def _endpoint_text(self) -> str:
        host = self.host_edit.text().strip()
        port = self.port_edit.text().strip() or "5000"
        return f"ftp://{host}:{port}" if host else "No FTP endpoint configured"

    def _toggle_connection_settings(self, expanded: bool) -> None:
        self.connection_settings.setVisible(expanded)
        self.settings_toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )

    def settings(self) -> ThreeDSFtpSettings:
        try:
            port = int(self.port_edit.text().strip())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError as exc:
            raise ValueError("FTP port must be between 1 and 65535.") from exc
        return ThreeDSFtpSettings(
            host=self.host_edit.text().strip(),
            port=port,
            username=self.user_edit.text().strip() or "anonymous",
            password=self.password_edit.text(),
            remote_root=self.root_edit.text().strip() or "/",
        )

    def save_settings(self) -> None:
        cfg = dict(self.config)
        devices = dict(cfg.get("devices", {}))
        devices["3ds"] = {
            "host": self.host_edit.text().strip(),
            "port": int(self.port_edit.text()),
            "username": self.user_edit.text().strip() or "anonymous",
            "password": self.password_edit.text(),
            "remote_root": self.root_edit.text().strip() or "/",
        }
        cfg["devices"] = devices
        save_config(cfg)
        self.config = cfg
        self.endpoint_label.setText(self._endpoint_text())

    def connect_3ds(self) -> None:
        if (self.connection_worker and self.connection_worker.isRunning()) or (
            self.worker and self.worker.isRunning()
        ):
            return
        try:
            settings = self.settings()
            self.save_settings()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid FTP settings", str(exc))
            return
        self._connected = False
        self.ftp_status.set_value("Connecting…")
        self.status.setText("Connecting to Nintendo 3DS FTP…")
        self.connection_worker = ThreeDSConnectionWorker(settings)
        self.connection_worker.succeeded.connect(self.connection_succeeded)
        self.connection_worker.failed.connect(self.connection_failed)
        self.connection_worker.finished.connect(self._connection_finished)
        self._update_controls()
        self.connection_worker.start()

    def connection_succeeded(self) -> None:
        self._connected = True
        self.ftp_status.set_value("Connected")
        self.status.setText(
            "Nintendo 3DS FTP connected. Select a game and deployment target."
        )
        self.settings_toggle.setChecked(False)
        self._update_controls()

    def connection_failed(self, message: str) -> None:
        self._connected = False
        self.ftp_status.set_value("Connection failed")
        self.status.setText(f"Nintendo 3DS FTP connection failed: {message}")
        self.settings_toggle.setChecked(True)
        self._update_controls()

    def _connection_finished(self) -> None:
        self.connection_worker = None
        self._update_controls()
        self._maybe_finish_close()

    def refresh_library(self) -> None:
        if self.library_worker and self.library_worker.isRunning():
            return
        self.game_list.clear()
        self._games = []
        self.target_combo.clear()
        self.artwork.clear()
        self.artwork.setText("No artwork")
        source = get_library_source(self.config)
        self.library_source = source

        if source.mode == "romm_api":
            if not source.romm_url.strip() or not source.api_token.strip():
                self.library_status.set_value("Needs setup")
                self.source_label.setText(
                    "RomM Server • URL or Client API Token is not configured."
                )
                self.status.setText("Configure the RomM Server library source first.")
                self._update_controls()
                return
            self.library_status.set_value("Loading…")
            self.source_label.setText(
                f"RomM Server • Loading compatible platforms from {source.romm_url}…"
            )
            self.status.setText("Loading compatible RomM library…")
            self.library_worker = RomMLibraryWorker(source.romm_url, source.api_token)
            self.library_worker.loaded.connect(self._romm_library_loaded)
            self.library_worker.failed.connect(self._romm_library_failed)
            self.library_worker.finished.connect(self._library_worker_finished)
            self._update_controls()
            self.library_worker.start()
            return

        root = self.library_root
        if root is None or not root.is_dir():
            self.library_status.set_value("Unavailable")
            self.source_label.setText("No local library directory is configured.")
            self.status.setText("Local library unavailable.")
            self._update_controls()
            return
        games = list(scan_games(root))
        self._games = games
        self.library_status.set_value(f"{len(games)} games")
        self.source_label.setText(f"Local library • {root}")
        for game in games:
            item = QListWidgetItem(
                f"{game.name}\n{game.source_platform} • {game.size:,} bytes"
            )
            item.setData(Qt.ItemDataRole.UserRole, game)
            self.game_list.addItem(item)
        if games:
            self.game_list.setCurrentRow(0)
        self._update_controls()

    def _romm_library_loaded(self, games) -> None:
        batch = list(games)
        self._games.extend(batch)
        self.library_status.set_value(f"{len(self._games)} games")
        self.source_label.setText(
            f"RomM Server • {len(self._games)} compatible library files"
        )
        self.status.setText(
            f"Loaded {len(self._games)} compatible games from RomM."
        )
        for game in batch:
            item = QListWidgetItem(
                f"{game.name}\n{game.platform} • {game.size:,} bytes"
            )
            item.setData(Qt.ItemDataRole.UserRole, game)
            self.game_list.addItem(item)
        if self._games and self.game_list.currentRow() < 0:
            self.game_list.setCurrentRow(0)
        self._update_controls()

    def _romm_library_failed(self, message: str) -> None:
        self.library_status.set_value("Load failed")
        self.source_label.setText(f"RomM Server • unable to load library: {message}")
        self.status.setText(f"RomM library load failed: {message}")
        self._update_controls()

    def _library_worker_finished(self) -> None:
        self.library_worker = None
        if self._games:
            self.library_status.set_value(f"{len(self._games)} games")
        self._update_controls()
        self._maybe_finish_close()

    def _selected_game(self):
        item = self.game_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def game_selected(self) -> None:
        game = self._selected_game()
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        if game is None:
            self.destination_edit.clear()
            self.details.setText("Select a game to see deployment options.")
            self.artwork.clear()
            self.artwork.setText("No artwork")
            self.target_combo.blockSignals(False)
            self._update_controls()
            return

        if isinstance(game, RomMRemoteGame):
            targets = available_targets(game.platform_slug)
            self.details.setText(
                f"{game.name}\n{game.platform} ({game.platform_slug}) • {game.size:,} bytes"
            )
            for target in targets:
                self.target_combo.addItem(target.label, target.key)
            self.target_combo.blockSignals(False)
            if targets:
                preferred = "native_gba" if game.platform_slug == "gba" else "retroarch"
                index = next(
                    (
                        i
                        for i in range(self.target_combo.count())
                        if self.target_combo.itemData(i) == preferred
                    ),
                    0,
                )
                self.target_combo.setCurrentIndex(index)
            self._load_artwork(game)
            self.target_changed()
            return

        self.target_combo.addItem("RetroArch ROM", "retroarch")
        self.target_combo.blockSignals(False)
        self.artwork.clear()
        self.artwork.setText("Local file")
        self.details.setText(f"{game.name}\nLocal library file")
        self.target_changed()

    def target_changed(self) -> None:
        game = self._selected_game()
        if game is None or self.target_combo.count() == 0:
            return
        target_key = str(self.target_combo.currentData())
        is_remote = isinstance(game, RomMRemoteGame)
        platform_slug = (
            game.platform_slug if is_remote else str(game.source_platform).lower()
        )
        platform_name = game.platform if is_remote else str(game.source_platform)
        filename = game.filename if is_remote else game.path.name
        self.destination_edit.setText(
            default_destination(target_key, platform_slug, filename)
        )
        target = next(
            (t for t in available_targets(platform_slug) if t.key == target_key),
            None,
        )
        if target is not None:
            self.details.setText(
                f"{game.name}\n{platform_name} ({platform_slug})\n\n{target.description}"
            )
        self._update_controls()

    def _load_artwork(self, game: RomMRemoteGame) -> None:
        self.artwork.clear()
        self.artwork.setText("Loading artwork…" if game.cover_url else "No artwork in RomM")
        if not game.cover_url:
            return
        if self.artwork_worker and self.artwork_worker.isRunning():
            return
        self.artwork_worker = RomMArtworkWorker(
            game.cover_url,
            self.library_source.api_token,
            self.library_source.romm_url,
        )
        self.artwork_worker.loaded.connect(self._artwork_loaded)
        self.artwork_worker.failed.connect(self._artwork_failed)
        self.artwork_worker.finished.connect(self._artwork_finished)
        self.artwork_worker.start()

    def _artwork_loaded(self, data: bytes) -> None:
        current = self._selected_game()
        if not isinstance(current, RomMRemoteGame):
            return
        if self.artwork_worker is None or current.cover_url != self.artwork_worker.url:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            self._artwork_failed("RomM returned an unsupported image.")
            return
        self.artwork.setPixmap(
            pixmap.scaled(
                204,
                204,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _artwork_failed(self, message: str) -> None:
        current = self._selected_game()
        if (
            isinstance(current, RomMRemoteGame)
            and self.artwork_worker is not None
            and current.cover_url == self.artwork_worker.url
        ):
            self.artwork.setText(f"Artwork unavailable\n{message}")

    def _artwork_finished(self) -> None:
        finished_url = self.artwork_worker.url if self.artwork_worker else ""
        self.artwork_worker = None
        current = self._selected_game()
        if (
            isinstance(current, RomMRemoteGame)
            and current.cover_url
            and current.cover_url != finished_url
            and not self._closing_requested
        ):
            self._load_artwork(current)
        self._maybe_finish_close()

    def _update_controls(self) -> None:
        ftp_busy = bool(
            (self.connection_worker and self.connection_worker.isRunning())
            or (self.worker and self.worker.isRunning())
        )
        library_busy = bool(self.library_worker and self.library_worker.isRunning())
        selected = self._selected_game() is not None
        target_key = str(self.target_combo.currentData() or "")
        target_uses_package_dialog = target_key in {"native_gba", "vc_cia"}
        self.connect_button.setEnabled(not ftp_busy)
        self.refresh_button.setEnabled(not library_busy and not ftp_busy)
        self.send_button.setEnabled(
            selected
            and not ftp_busy
            and not library_busy
            and (self._connected or target_uses_package_dialog)
        )
        self.cancel_button.setEnabled(bool(self.worker and self.worker.isRunning()))
        self.cancel_button.setVisible(bool(self.worker and self.worker.isRunning()))
        self.progress.setVisible(bool(self.worker and self.worker.isRunning()))
        for widget in (
            self.host_edit,
            self.port_edit,
            self.user_edit,
            self.password_edit,
            self.root_edit,
        ):
            widget.setEnabled(not ftp_busy)
        self.settings_toggle.setEnabled(not ftp_busy)
        self.destination_edit.setEnabled(not ftp_busy and not library_busy)
        self.target_combo.setEnabled(selected and not ftp_busy and not library_busy)

    def send_selected(self) -> None:
        selected = self._selected_game()
        if selected is None:
            return
        target_key = str(self.target_combo.currentData() or "retroarch")
        if target_key in {"native_gba", "vc_cia"}:
            if isinstance(selected, RomMRemoteGame) and selected.platform_slug == "gba":
                from .gba_vc_deploy import GbaVcDeployDialog

                GbaVcDeployDialog(self.config, selected, target_key, self).exec()
                return
            QMessageBox.information(
                self,
                "CIA packaging unavailable",
                "This CIA packaging route is currently available for RomM-backed GBA titles. "
                "Local-file and other-platform CIA packaging remains explicit until a matching packager is implemented.",
            )
            return

        if isinstance(selected, RomMRemoteGame):
            source = None
            remote_game = selected
        else:
            source = selected.path
            remote_game = None
            if not source.is_file():
                QMessageBox.warning(
                    self,
                    "File not found",
                    "The selected local library file is no longer available.",
                )
                return

        destination = self.destination_edit.text().strip()
        if not destination:
            QMessageBox.warning(
                self,
                "Destination required",
                "Enter a remote destination first.",
            )
            return
        try:
            settings = self.settings()
            self.save_settings()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid FTP settings", str(exc))
            return

        self.progress.setValue(0)
        self.status.setText(f"Preparing {selected.name}…")
        self.worker = ThreeDSTransferWorker(
            settings,
            source,
            destination,
            remote_game=remote_game,
            romm_url=self.library_source.romm_url,
            romm_token=self.library_source.api_token,
        )
        self.worker.status_changed.connect(self.status.setText)
        self.worker.progress.connect(self.worker_progress)
        self.worker.completed.connect(self.worker_completed)
        self.worker.failed.connect(self.worker_failed)
        self.worker.finished.connect(self._worker_finished)
        self._update_controls()
        self.worker.start()

    def worker_progress(self, done: int) -> None:
        selected = self._selected_game()
        if selected is None:
            return
        total = (
            selected.size
            if isinstance(selected, RomMRemoteGame)
            else selected.path.stat().st_size
            if selected.path.is_file()
            else 0
        )
        self.progress.setValue(int(done * 100 / total) if total else 100)

    def worker_completed(self, result: str) -> None:
        self.status.setText(
            {
                "copied": "Upload complete and size verified.",
                "resumed": "Partial upload resumed and size verified.",
                "skipped": "The 3DS already has the same-size file; nothing was overwritten.",
                "different": "A different-size file already exists on the 3DS. Nothing was overwritten.",
                "cancelled": "Transfer cancelled.",
            }.get(result, result)
        )
        if result == "different":
            QMessageBox.warning(self, "3DS file already exists", self.status.text())

    def worker_failed(self, message: str) -> None:
        self.status.setText(f"Transfer failed: {message}")

    def _worker_finished(self) -> None:
        self.worker = None
        self.progress.setVisible(False)
        self._update_controls()
        self._maybe_finish_close()

    def cancel_transfer(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status.setText("Cancelling transfer…")
            self.cancel_button.setEnabled(False)

    def _running_workers(self) -> tuple[QThread, ...]:
        return tuple(
            worker
            for worker in (
                self.library_worker,
                self.artwork_worker,
                self.connection_worker,
                self.worker,
            )
            if worker is not None and worker.isRunning()
        )

    def _maybe_finish_close(self) -> None:
        if self._closing_requested and not self._running_workers():
            QTimer.singleShot(0, self.close)

    def closeEvent(self, event) -> None:
        running = self._running_workers()
        if not running:
            super().closeEvent(event)
            return

        self._closing_requested = True
        if self.library_worker and self.library_worker.isRunning():
            self.library_worker.requestInterruption()
        if self.artwork_worker and self.artwork_worker.isRunning():
            self.artwork_worker.requestInterruption()
        if self.worker and self.worker.isRunning():
            self.worker.cancel()

        self.status.setText("Finishing the current background operation before closing…")
        self.setEnabled(False)
        event.ignore()
