from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from urllib import error, request

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from .config import save_config
from .library_sources import get_library_source
from .romm import scan_games
from .romm_remote import RomMRemoteGame, download_rom
from .romm_remote_worker import RomMLibraryWorker
from .three_ds_ftp import ThreeDSFtpBackend, ThreeDSFtpSettings
from .three_ds_targets import available_targets, default_destination


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

    def __init__(self, url: str, token: str):
        super().__init__()
        self.url = url
        self.token = token

    def run(self) -> None:
        try:
            headers = {
                "User-Agent": "RommHeld",
                "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*",
            }
            if self.token.strip():
                headers["Authorization"] = f"Bearer {self.token.strip()}"
            with request.urlopen(request.Request(self.url, headers=headers), timeout=10) as response:
                data = response.read(8 * 1024 * 1024 + 1)
            if len(data) > 8 * 1024 * 1024:
                raise ValueError("Artwork is larger than the 8 MiB safety limit.")
            self.loaded.emit(data)
        except error.HTTPError as exc:
            self.failed.emit(f"Artwork request returned HTTP {exc.code}.")
        except (error.URLError, TimeoutError, ValueError) as exc:
            self.failed.emit(str(exc))


class ThreeDSTransferWorker(QThread):
    progress = Signal(int)
    status_changed = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, settings, source, destination, *, remote_game=None, romm_url="", romm_token=""):
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
        return download_rom(self.romm_url, self.romm_token, self.remote_game, self._temporary_path)

    def run(self) -> None:
        try:
            source = self._resolve_source()
            name = self.remote_game.name if self.remote_game else source.name
            self.status_changed.emit(f"Transferring {name} to the 3DS…")
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
    """3DS deployment surface for compatible local or RomM library content."""

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

        self.setWindowTitle("Nintendo 3DS Manager")
        self.resize(1040, 760)

        saved = config.get("devices", {}).get("3ds", {})
        self.host_edit = QLineEdit(str(saved.get("host", "")))
        self.port_edit = QLineEdit(str(saved.get("port", 5000)))
        self.user_edit = QLineEdit(str(saved.get("username", "anonymous")))
        self.password_edit = QLineEdit(str(saved.get("password", "")))
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.root_edit = QLineEdit(str(saved.get("remote_root", "/")))

        self.connect_button = QPushButton("Connect")
        self.refresh_button = QPushButton("Refresh Library")
        self.connect_button.clicked.connect(self.connect_3ds)
        self.refresh_button.clicked.connect(self.refresh_library)

        form = QFormLayout()
        for label, widget in (
            ("Host:", self.host_edit),
            ("Port:", self.port_edit),
            ("Username:", self.user_edit),
            ("Password:", self.password_edit),
            ("Remote root:", self.root_edit),
        ):
            form.addRow(label, widget)

        connection_row = QHBoxLayout()
        connection_row.addWidget(self.connect_button)
        connection_row.addWidget(self.refresh_button)
        connection_row.addStretch()

        self.status = QLabel("Ready. RomM and 3DS connections operate independently.")
        self.status.setWordWrap(True)
        self.source_label = QLabel("Library source: not loaded")
        self.source_label.setWordWrap(True)

        self.game_list = QListWidget()
        self.game_list.itemSelectionChanged.connect(self.game_selected)

        self.artwork = QLabel("No artwork")
        self.artwork.setFixedSize(180, 180)
        self.artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.details = QLabel("Select a game to see deployment options.")
        self.details.setWordWrap(True)

        self.target_combo = QComboBox()
        self.target_combo.currentIndexChanged.connect(self.target_changed)

        self.destination_edit = QLineEdit()
        self.destination_edit.setPlaceholderText("Remote destination")
        self.send_button = QPushButton("Deploy Selected Game")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.send_button.clicked.connect(self.send_selected)
        self.cancel_button.clicked.connect(self.cancel_transfer)

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Deploy as:"))
        target_row.addWidget(self.target_combo, 1)
        target_row.addWidget(QLabel("Destination:"))
        target_row.addWidget(self.destination_edit, 2)
        target_row.addWidget(self.send_button)
        target_row.addWidget(self.cancel_button)

        detail_row = QHBoxLayout()
        detail_row.addWidget(self.artwork)
        detail_row.addWidget(self.details, 1)

        self.progress = QProgressBar()

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(connection_row)
        layout.addWidget(self.status)
        layout.addWidget(self.source_label)
        layout.addWidget(QLabel("Compatible RomM library:"))
        layout.addWidget(self.game_list, 1)
        layout.addLayout(detail_row)
        layout.addLayout(target_row)
        layout.addWidget(self.progress)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        layout.addWidget(close)

        self.refresh_library()
        self._update_controls()

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

    def connect_3ds(self) -> None:
        if (self.connection_worker and self.connection_worker.isRunning()) or (self.worker and self.worker.isRunning()):
            return
        try:
            settings = self.settings()
            self.save_settings()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid FTP settings", str(exc))
            return
        self.status.setText("Connecting to 3DS FTP…")
        self.connection_worker = ThreeDSConnectionWorker(settings)
        self.connection_worker.succeeded.connect(self.connection_succeeded)
        self.connection_worker.failed.connect(self.connection_failed)
        self.connection_worker.finished.connect(self._connection_finished)
        self._update_controls()
        self.connection_worker.start()

    def connection_succeeded(self) -> None:
        self._connected = True
        self.status.setText("3DS FTP connected. RomM is independent of this connection.")
        self._update_controls()

    def connection_failed(self, message: str) -> None:
        self._connected = False
        self.status.setText(f"3DS FTP connection failed: {message}")
        self._update_controls()

    def _connection_finished(self) -> None:
        self.connection_worker = None
        self._update_controls()

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
                self.source_label.setText("RomM Server • URL or Client API Token is not configured.")
                self.status.setText("Configure the RomM Server library source first.")
                self._update_controls()
                return
            self.source_label.setText(f"RomM Server • Loading compatible platforms from {source.romm_url}…")
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
            self.source_label.setText("No local library directory is configured.")
            self.status.setText("Local library unavailable.")
            self._update_controls()
            return
        games = list(scan_games(root))
        self._games = games
        self.source_label.setText(f"{root} • {len(games)} library files")
        for game in games:
            item = QListWidgetItem(f"{game.name} • {game.source_platform} • {game.size:,} bytes")
            item.setData(Qt.ItemDataRole.UserRole, game)
            self.game_list.addItem(item)
        if games:
            self.game_list.setCurrentRow(0)
        self._update_controls()

    def _romm_library_loaded(self, games) -> None:
        self._games = list(games)
        self.source_label.setText(f"RomM Server • {len(self._games)} compatible library files")
        self.status.setText(f"RomM library loaded: {len(self._games)} compatible files.")
        for game in self._games:
            item = QListWidgetItem(f"{game.name} • {game.platform} • {game.size:,} bytes")
            item.setData(Qt.ItemDataRole.UserRole, game)
            self.game_list.addItem(item)
        if self._games:
            self.game_list.setCurrentRow(0)
        self._update_controls()

    def _romm_library_failed(self, message: str) -> None:
        self.source_label.setText(f"RomM Server • unable to load library: {message}")
        self.status.setText(f"RomM library load failed: {message}")
        self._update_controls()

    def _library_worker_finished(self) -> None:
        self.library_worker = None
        self._update_controls()

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
            self.target_combo.blockSignals(False)
            self._update_controls()
            return

        if isinstance(game, RomMRemoteGame):
            targets = available_targets(game.platform_slug)
            self.details.setText(
                f"{game.name}\n{game.platform} ({game.platform_slug}) • {game.size:,} bytes\n"
                "RomM artwork is used directly when an artwork URL is available."
            )
            for target in targets:
                self.target_combo.addItem(target.label, target.key)
            self.target_combo.blockSignals(False)
            if targets:
                preferred = "native_gba" if game.platform_slug == "gba" else "retroarch"
                index = next((i for i in range(self.target_combo.count()) if self.target_combo.itemData(i) == preferred), 0)
                self.target_combo.setCurrentIndex(index)
            self._load_artwork(game)
            self.target_changed()
            return

        self.target_combo.addItem("RetroArch ROM", "retroarch")
        self.target_combo.blockSignals(False)
        self.details.setText(f"{game.name}\nLocal library file")
        self.target_changed()

    def target_changed(self) -> None:
        game = self._selected_game()
        if game is None or self.target_combo.count() == 0:
            return
        target_key = str(self.target_combo.currentData())
        platform_slug = game.platform_slug if isinstance(game, RomMRemoteGame) else str(game.source_platform).lower()
        filename = game.filename if isinstance(game, RomMRemoteGame) else game.path.name
        self.destination_edit.setText(default_destination(target_key, platform_slug, filename))
        target = next((t for t in available_targets(platform_slug) if t.key == target_key), None)
        if target is not None:
            self.details.setText(f"{game.name}\n{game.platform} ({platform_slug})\n\n{target.description}")
        self._update_controls()

    def _load_artwork(self, game: RomMRemoteGame) -> None:
        if self.artwork_worker and self.artwork_worker.isRunning():
            return
        self.artwork.clear()
        self.artwork.setText("Loading artwork…" if game.cover_url else "No artwork in RomM")
        if not game.cover_url:
            return
        self.artwork_worker = RomMArtworkWorker(game.cover_url, self.library_source.api_token)
        self.artwork_worker.loaded.connect(self._artwork_loaded)
        self.artwork_worker.failed.connect(self._artwork_failed)
        self.artwork_worker.finished.connect(self._artwork_finished)
        self.artwork_worker.start()

    def _artwork_loaded(self, data: bytes) -> None:
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            self._artwork_failed("RomM returned an unsupported image.")
            return
        self.artwork.setPixmap(
            pixmap.scaled(180, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )

    def _artwork_failed(self, message: str) -> None:
        self.artwork.setText(f"Artwork unavailable\n{message}")

    def _artwork_finished(self) -> None:
        self.artwork_worker = None

    def _update_controls(self) -> None:
        ftp_busy = bool((self.connection_worker and self.connection_worker.isRunning()) or (self.worker and self.worker.isRunning()))
        library_busy = bool(self.library_worker and self.library_worker.isRunning())
        selected = self._selected_game() is not None
        self.connect_button.setEnabled(not ftp_busy)
        self.refresh_button.setEnabled(not library_busy and not ftp_busy)
        self.send_button.setEnabled(self._connected and selected and not ftp_busy and not library_busy)
        self.cancel_button.setEnabled(bool(self.worker and self.worker.isRunning()))
        for widget in (self.host_edit, self.port_edit, self.user_edit, self.password_edit, self.root_edit):
            widget.setEnabled(not ftp_busy)
        self.destination_edit.setEnabled(not ftp_busy and not library_busy)
        self.target_combo.setEnabled(selected and not ftp_busy and not library_busy)

    def send_selected(self) -> None:
        selected = self._selected_game()
        if selected is None:
            return
        target_key = str(self.target_combo.currentData() or "retroarch")
        if target_key == "native_gba":
            QMessageBox.information(
                self,
                "GBA native packaging setup",
                "Nintendo GBA native deployment uses AGB_FIRM and therefore requires the CIA packager plus your user-supplied donor assets. The next packaging step will make this automatic.",
            )
            return
        if target_key == "vc_cia":
            QMessageBox.information(
                self,
                "Virtual Console packaging setup",
                "Virtual Console CIA packaging is not yet enabled for this platform. The library browser is already prepared to hand a selected ROM and its artwork to the appropriate packager.",
            )
            return

        if isinstance(selected, RomMRemoteGame):
            source = None
            remote_game = selected
        else:
            source = selected.path
            remote_game = None
            if not source.is_file():
                QMessageBox.warning(self, "File not found", "The selected local library file is no longer available.")
                return

        destination = self.destination_edit.text().strip()
        if not destination:
            QMessageBox.warning(self, "Destination required", "Enter a remote destination first.")
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
        total = selected.size if isinstance(selected, RomMRemoteGame) else selected.path.stat().st_size if selected.path.is_file() else 0
        self.progress.setValue(int(done * 100 / total) if total else 100)

    def worker_completed(self, result: str) -> None:
        self.status.setText(
            {
                "copied": "File uploaded and size verified.",
                "resumed": "Partial file resumed and size verified.",
                "skipped": "Remote file already has the same size; nothing was overwritten.",
                "different": "A different-size remote file exists. No overwrite was performed.",
                "cancelled": "Transfer cancelled.",
            }.get(result, result)
        )
        if result == "different":
            QMessageBox.warning(self, "3DS file already exists", self.status.text())

    def worker_failed(self, message: str) -> None:
        self.status.setText(f"Transfer failed: {message}")

    def _worker_finished(self) -> None:
        self.worker = None
        self._update_controls()

    def cancel_transfer(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status.setText("Cancelling…")
            self.cancel_button.setEnabled(False)

    def closeEvent(self, event) -> None:
        if self.library_worker and self.library_worker.isRunning():
            self.library_worker.requestInterruption()
            self.library_worker.wait(1500)
        if self.artwork_worker and self.artwork_worker.isRunning():
            self.artwork_worker.requestInterruption()
            self.artwork_worker.wait(1500)
        if self.connection_worker and self.connection_worker.isRunning():
            self.connection_worker.wait(1500)
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
        super().closeEvent(event)
