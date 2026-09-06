from __future__ import annotations

import posixpath
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .design_tokens import brand_for_platform
from .ftp_file_safety import destructive_path_risk
from .ftp_filesystem import RemoteEntry, ftp_filesystem_for_console
from .three_ds_ftp import ThreeDSFtpSettings
from .ui_components import AccentButton, SectionHeader, StatusPill, SurfaceCard
from .vita_ftp import VitaFtpSettings


Settings = ThreeDSFtpSettings | VitaFtpSettings


def _console_family(console: str) -> str:
    normalized = console.strip().casefold()
    if normalized in {"3ds", "nintendo 3ds"}:
        return "3ds"
    if normalized in {"vita", "ps vita", "playstation vita", "pstv", "playstation tv"}:
        return "vita"
    raise ValueError(f"FTP file manager is not supported for console: {console}")


def _display_console(console: str) -> str:
    return "Nintendo 3DS" if _console_family(console) == "3ds" else "PlayStation Vita"


def _endpoint(settings: Settings) -> str:
    return f"ftp://{settings.host}:{settings.port}"


def _join_relative(parent: str, name: str) -> str:
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError(f"Invalid remote name: {name!r}")
    parent = parent.strip("/")
    return posixpath.join(parent, name) if parent else name


def _parent_relative(path: str) -> str:
    cleaned = path.strip("/")
    if not cleaned:
        return ""
    parent = posixpath.dirname(cleaned)
    return "" if parent == "." else parent


def _format_size(size: int) -> str:
    value = float(max(0, size))
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024.0 or unit == "TiB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{int(size)} B"


class FtpFileOperationWorker(QThread):
    completed = Signal(str, object)
    failed = Signal(str, str)
    progress = Signal(int, int)
    status_changed = Signal(str)

    def __init__(
        self,
        console: str,
        settings: Settings,
        operation: str,
        *,
        remote_path: str = "",
        destination_path: str = "",
        local_path: Path | None = None,
        overwrite: bool = False,
    ):
        super().__init__()
        self.console = console
        self.settings = settings
        self.operation = operation
        self.remote_path = remote_path
        self.destination_path = destination_path
        self.local_path = local_path
        self.overwrite = overwrite
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()
        self.requestInterruption()

    def _progress(self, done: int, total: int) -> None:
        self.progress.emit(max(0, int(done)), max(0, int(total)))

    def run(self) -> None:
        adapter = ftp_filesystem_for_console(self.console, self.settings)
        try:
            if self.cancel_event.is_set():
                raise InterruptedError("FTP operation cancelled.")
            self.status_changed.emit(f"Connecting to {_display_console(self.console)} FTP…")
            cwd = adapter.connect()
            if self.cancel_event.is_set():
                raise InterruptedError("FTP operation cancelled.")

            if self.operation == "list":
                self.status_changed.emit("Loading remote directory…")
                entries = adapter.list_directory(self.remote_path)
                free = adapter.available_space() if adapter.capabilities.free_space else None
                self.completed.emit(
                    self.operation,
                    {
                        "entries": entries,
                        "cwd": cwd,
                        "free_space": free,
                    },
                )
                return

            if self.operation == "upload":
                if self.local_path is None:
                    raise ValueError("Upload source is required.")
                total = self.local_path.stat().st_size
                self.status_changed.emit(f"Uploading {self.local_path.name}…")
                result, size = adapter.upload(
                    self.local_path,
                    self.remote_path,
                    overwrite=self.overwrite,
                    cancel_event=self.cancel_event,
                    progress=lambda done: self._progress(done, total),
                )
                if result == "different" and not self.overwrite:
                    self.completed.emit(self.operation, {"result": "different", "size": 0})
                    return
                if result == "cancelled":
                    raise InterruptedError("FTP upload cancelled.")
                self.completed.emit(self.operation, {"result": result, "size": size})
                return

            if self.operation == "download":
                if self.local_path is None:
                    raise ValueError("Download destination is required.")
                expected = adapter._remote_size(self.remote_path) or 0
                self.status_changed.emit(f"Downloading {posixpath.basename(self.remote_path)}…")
                result, size = adapter.download(
                    self.remote_path,
                    self.local_path,
                    overwrite=self.overwrite,
                    cancel_event=self.cancel_event,
                    progress=lambda done: self._progress(done, expected),
                )
                self.completed.emit(self.operation, {"result": result, "size": size})
                return

            if self.operation == "mkdir":
                adapter.make_directory(self.remote_path)
                self.completed.emit(self.operation, self.remote_path)
                return

            if self.operation == "rename":
                adapter.rename(self.remote_path, self.destination_path)
                self.completed.emit(self.operation, self.destination_path)
                return

            if self.operation == "delete_file":
                adapter.delete_file(self.remote_path)
                self.completed.emit(self.operation, self.remote_path)
                return

            if self.operation == "remove_directory":
                adapter.remove_directory(self.remote_path)
                self.completed.emit(self.operation, self.remote_path)
                return

            raise ValueError(f"Unknown FTP file operation: {self.operation}")
        except InterruptedError:
            self.completed.emit(self.operation, {"result": "cancelled"})
        except Exception as exc:
            self.failed.emit(self.operation, str(exc))
        finally:
            adapter.close()


class FtpFileManagerDialog(QDialog):
    """Contextual remote file browser shared by the supported console FTP transports."""

    def __init__(self, console: str, settings: Settings, parent=None):
        super().__init__(parent)
        self.console = console
        self.console_family = _console_family(console)
        self.console_name = _display_console(console)
        self.settings = settings
        self.current_path = ""
        self.worker: FtpFileOperationWorker | None = None
        self._pending_upload: tuple[Path, str] | None = None
        self._closing_requested = False

        if not settings.host.strip():
            raise ValueError(f"{self.console_name} FTP host is required.")

        accent = brand_for_platform(self.console_family).accent
        root_label = settings.remote_root

        self.setWindowTitle(f"{self.console_name} FTP Files")
        self.resize(940, 680)
        self.setMinimumSize(760, 560)

        header = SectionHeader(
            f"{self.console_name} FTP files",
            "Browse and manage files on the live console. Normal game deployment remains in Library; this is an advanced filesystem tool.",
        )

        self.connection_status = StatusPill("FTP", "Connecting…")
        endpoint_label = QLabel(f"{_endpoint(settings)}  ·  Root: {root_label}")
        endpoint_label.setProperty("secondary", True)
        endpoint_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.space_label = QLabel(
            "Free space: checking…" if self.console_family == "3ds" else "Free space: unavailable over VitaShell FTP"
        )
        self.space_label.setProperty("secondary", True)
        connection_row = QHBoxLayout()
        connection_row.setSpacing(8)
        connection_row.addWidget(self.connection_status)
        connection_row.addWidget(endpoint_label, 1)
        connection_row.addWidget(self.space_label)

        connection_card = SurfaceCard()
        connection_card.content.addLayout(connection_row)

        self.up_button = QPushButton("Up")
        self.up_button.clicked.connect(self.go_up)
        self.path_label = QLabel("/")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.copy_path_button = QPushButton("Copy path")
        self.copy_path_button.clicked.connect(self.copy_current_path)
        self.refresh_button = AccentButton("Refresh", accent)
        self.refresh_button.clicked.connect(self.refresh_directory)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        path_row.addWidget(self.up_button)
        path_row.addWidget(self.path_label, 1)
        path_row.addWidget(self.copy_path_button)
        path_row.addWidget(self.refresh_button)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Size"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.cellDoubleClicked.connect(self._row_activated)

        browser_card = SurfaceCard()
        browser_card.content.addLayout(path_row)
        browser_card.content.addWidget(self.table, 1)

        self.upload_button = AccentButton("Upload file", accent)
        self.download_button = QPushButton("Download")
        self.new_folder_button = QPushButton("New folder")
        self.rename_button = QPushButton("Rename")
        self.delete_button = QPushButton("Delete")
        self.upload_button.clicked.connect(self.upload_file)
        self.download_button.clicked.connect(self.download_selected)
        self.new_folder_button.clicked.connect(self.create_folder)
        self.rename_button.clicked.connect(self.rename_selected)
        self.delete_button.clicked.connect(self.delete_selected)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addWidget(self.upload_button)
        action_row.addWidget(self.download_button)
        action_row.addWidget(self.new_folder_button)
        action_row.addWidget(self.rename_button)
        action_row.addWidget(self.delete_button)
        action_row.addStretch(1)

        self.status_label = QLabel("Connecting…")
        self.status_label.setWordWrap(True)
        self.status_label.setProperty("secondary", True)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        self.cancel_button = QPushButton("Cancel transfer")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_operation)
        operation_row = QHBoxLayout()
        operation_row.addWidget(self.status_label, 1)
        operation_row.addWidget(self.cancel_button)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close = QPushButton("Done")
        close.clicked.connect(self.close)
        close_row.addWidget(close)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(header)
        layout.addWidget(connection_card)
        layout.addWidget(browser_card, 1)
        layout.addLayout(action_row)
        layout.addWidget(self.progress)
        layout.addLayout(operation_row)
        layout.addLayout(close_row)

        self._update_actions()
        self.refresh_directory()

    def _remote_display_path(self) -> str:
        root = self.settings.remote_root.rstrip("/") or "/"
        if not self.current_path:
            return root
        if root == "/":
            return "/" + self.current_path
        return root + "/" + self.current_path

    def _selected_entry(self) -> RemoteEntry | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        if item is None:
            return None
        entry = item.data(Qt.ItemDataRole.UserRole)
        return entry if isinstance(entry, RemoteEntry) else None

    def _set_busy(self, busy: bool, *, transfer: bool = False) -> None:
        self.table.setEnabled(not busy)
        self.up_button.setEnabled(not busy and bool(self.current_path))
        self.refresh_button.setEnabled(not busy)
        self.upload_button.setEnabled(not busy)
        self.new_folder_button.setEnabled(not busy)
        if busy:
            self.download_button.setEnabled(False)
            self.rename_button.setEnabled(False)
            self.delete_button.setEnabled(False)
        else:
            self._selection_changed()
        self.cancel_button.setVisible(busy and transfer)
        self.progress.setVisible(busy and transfer)
        if not busy:
            self.progress.setValue(0)

    def _update_actions(self) -> None:
        busy = self.worker is not None and self.worker.isRunning()
        self._set_busy(busy, transfer=False)

    def _selection_changed(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        entry = self._selected_entry()
        self.download_button.setEnabled(entry is not None and not entry.is_dir)
        self.rename_button.setEnabled(entry is not None)
        self.delete_button.setEnabled(entry is not None)
        self.up_button.setEnabled(bool(self.current_path))

    def _row_activated(self, row: int, column: int) -> None:
        del column
        item = self.table.item(row, 0)
        entry = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if isinstance(entry, RemoteEntry) and entry.is_dir:
            self.current_path = entry.path
            self.refresh_directory()

    def _start_worker(
        self,
        operation: str,
        *,
        remote_path: str = "",
        destination_path: str = "",
        local_path: Path | None = None,
        overwrite: bool = False,
        transfer: bool = False,
    ) -> None:
        if self.worker is not None:
            return
        self.worker = FtpFileOperationWorker(
            self.console,
            self.settings,
            operation,
            remote_path=remote_path,
            destination_path=destination_path,
            local_path=local_path,
            overwrite=overwrite,
        )
        self.worker.completed.connect(self._operation_completed)
        self.worker.failed.connect(self._operation_failed)
        self.worker.progress.connect(self._operation_progress)
        self.worker.status_changed.connect(self.status_label.setText)
        self.worker.finished.connect(self._worker_finished)
        self._set_busy(True, transfer=transfer)
        self.worker.start()

    def refresh_directory(self) -> None:
        if self.worker is not None:
            return
        self.path_label.setText(self._remote_display_path())
        self.connection_status.set_value("Connecting…")
        self._start_worker("list", remote_path=self.current_path)

    def go_up(self) -> None:
        if self.worker is not None:
            return
        self.current_path = _parent_relative(self.current_path)
        self.refresh_directory()

    def copy_current_path(self) -> None:
        QApplication.clipboard().setText(self._remote_display_path())
        self.status_label.setText("Remote path copied to clipboard.")

    def upload_file(self) -> None:
        if self.worker is not None:
            return
        raw, _ = QFileDialog.getOpenFileName(self, "Choose file to upload")
        if not raw:
            return
        source = Path(raw).expanduser()
        remote = _join_relative(self.current_path, source.name)
        self._pending_upload = (source, remote)
        self._start_worker("upload", remote_path=remote, local_path=source, transfer=True)

    def download_selected(self) -> None:
        entry = self._selected_entry()
        if entry is None or entry.is_dir or self.worker is not None:
            return
        raw, _ = QFileDialog.getSaveFileName(self, "Download remote file", entry.name)
        if not raw:
            return
        destination = Path(raw).expanduser()
        overwrite = False
        if destination.exists():
            answer = QMessageBox.question(
                self,
                "Replace local file?",
                f"{destination} already exists. Download to a temporary file and replace it only after size verification?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            overwrite = True
        self._start_worker(
            "download",
            remote_path=entry.path,
            local_path=destination,
            overwrite=overwrite,
            transfer=True,
        )

    def create_folder(self) -> None:
        if self.worker is not None:
            return
        name, ok = QInputDialog.getText(self, "New remote folder", "Folder name")
        name = name.strip()
        if not ok or not name:
            return
        try:
            remote = _join_relative(self.current_path, name)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid folder name", str(exc))
            return
        self._start_worker("mkdir", remote_path=remote)

    def _confirm_sensitive_change(self, path: str, verb: str) -> bool:
        risk = destructive_path_risk(self.console, path)
        message = f"{risk.message}\n\nSelected path: {self._display_path_for_relative(path)}\n\n{verb} this item?"
        if risk.level == "critical":
            message += "\n\nThis is a console-sensitive location. RommHeld cannot automatically repair damage caused by an incorrect change."
        answer = QMessageBox.warning(
            self,
            risk.title if risk.level != "normal" else f"{verb} remote item",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _display_path_for_relative(self, path: str) -> str:
        root = self.settings.remote_root.rstrip("/") or "/"
        cleaned = path.strip("/")
        if not cleaned:
            return root
        return "/" + cleaned if root == "/" else root + "/" + cleaned

    def rename_selected(self) -> None:
        entry = self._selected_entry()
        if entry is None or self.worker is not None:
            return
        name, ok = QInputDialog.getText(
            self,
            "Rename remote item",
            "New name",
            text=entry.name,
        )
        name = name.strip()
        if not ok or not name or name == entry.name:
            return
        try:
            destination = _join_relative(self.current_path, name)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid remote name", str(exc))
            return
        if destructive_path_risk(self.console, entry.path).level != "normal":
            if not self._confirm_sensitive_change(entry.path, "Rename"):
                return
        self._start_worker(
            "rename",
            remote_path=entry.path,
            destination_path=destination,
        )

    def delete_selected(self) -> None:
        entry = self._selected_entry()
        if entry is None or self.worker is not None:
            return
        verb = "Remove empty folder" if entry.is_dir else "Delete"
        if not self._confirm_sensitive_change(entry.path, verb):
            return
        operation = "remove_directory" if entry.is_dir else "delete_file"
        self._start_worker(operation, remote_path=entry.path)

    def cancel_operation(self) -> None:
        if self.worker is None or not self.worker.isRunning():
            return
        self.cancel_button.setEnabled(False)
        self.status_label.setText("Cancelling FTP transfer…")
        self.worker.cancel()

    def _operation_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(max(0, min(100, int(done * 100 / total))))
        else:
            self.progress.setRange(0, 0)

    def _populate_entries(self, entries: list[RemoteEntry]) -> None:
        self.table.setRowCount(0)
        for entry in entries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            name = QTableWidgetItem(entry.name)
            name.setData(Qt.ItemDataRole.UserRole, entry)
            kind = QTableWidgetItem("Folder" if entry.is_dir else "File")
            size = QTableWidgetItem("—" if entry.is_dir else _format_size(entry.size))
            size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, kind)
            self.table.setItem(row, 2, size)

    def _operation_completed(self, operation: str, payload: object) -> None:
        if operation == "list" and isinstance(payload, dict):
            entries = payload.get("entries", [])
            if isinstance(entries, list):
                self._populate_entries(entries)
            free = payload.get("free_space")
            self.connection_status.set_value("Connected")
            if isinstance(free, int) and free >= 0:
                self.space_label.setText(f"Free space: {_format_size(free)}")
            elif self.console_family == "3ds":
                self.space_label.setText("Free space: unavailable from server")
            self.status_label.setText(f"Loaded {self.table.rowCount()} remote item(s).")
            self.path_label.setText(self._remote_display_path())
            return

        result = payload.get("result") if isinstance(payload, dict) else None
        if result == "different" and operation == "upload" and self._pending_upload is not None:
            source, remote = self._pending_upload
            answer = QMessageBox.question(
                self,
                "Replace remote file?",
                f"A different-size file already exists at {self._display_path_for_relative(remote)}. Upload to a verified staging file and replace the existing file only after verification?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._pending_upload = None
                self.worker = None
                self._start_worker(
                    "upload",
                    remote_path=remote,
                    local_path=source,
                    overwrite=True,
                    transfer=True,
                )
                return
            self._pending_upload = None
            self.status_label.setText("Remote replacement cancelled; existing file was preserved.")
            return

        if result == "cancelled":
            self.status_label.setText("FTP operation cancelled. Existing destination data was preserved where applicable.")
            return

        self._pending_upload = None
        labels = {
            "upload": "Upload completed.",
            "download": "Download completed and verified.",
            "mkdir": "Remote folder created.",
            "rename": "Remote item renamed.",
            "delete_file": "Remote file deleted.",
            "remove_directory": "Empty remote folder removed.",
        }
        self.status_label.setText(labels.get(operation, "FTP operation completed."))

    def _operation_failed(self, operation: str, message: str) -> None:
        self._pending_upload = None
        self.connection_status.set_value("Error")
        self.status_label.setText(f"{operation.replace('_', ' ').capitalize()} failed: {message}")
        QMessageBox.warning(self, "FTP file operation failed", message)

    def _worker_finished(self) -> None:
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.deleteLater()
        self.cancel_button.setEnabled(True)
        self.progress.setRange(0, 100)
        self._set_busy(False)

        if self._closing_requested:
            self.close()
            return

        # Refresh after mutations/transfers, but not after a plain list or a cancelled operation.
        if worker is not None and worker.operation not in {"list", "download"}:
            self.refresh_directory()

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            self._closing_requested = True
            self.worker.cancel()
            self.status_label.setText("Cancelling the active FTP operation before closing…")
            event.ignore()
            return
        super().closeEvent(event)


__all__ = ["FtpFileManagerDialog", "FtpFileOperationWorker"]
