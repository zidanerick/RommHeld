from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QPushButton, QVBoxLayout

from .app import MainWindow as BaseMainWindow, ThreeDSFtpDialog
from .config import load_config
from .local_storage_ui import MountedStorageDialog


class DeviceDashboardWindow(BaseMainWindow):
    """RommHeld main window with persistent per-device management sections."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.setWindowTitle("RommHeld")
        self._three_ds_dialog: ThreeDSFtpDialog | None = None
        self._vita_storage_dialog: MountedStorageDialog | None = None
        self._three_ds_storage_dialog: MountedStorageDialog | None = None
        self._build_device_sections()

    def _build_device_sections(self) -> None:
        central = self.centralWidget()
        if central is None or central.layout() is None:
            return

        layout = central.layout()
        splitter_item = next(
            (layout.itemAt(i) for i in range(layout.count())
             if layout.itemAt(i).widget() is not None and hasattr(layout.itemAt(i).widget(), "count")),
            None,
        )
        splitter = splitter_item.widget() if splitter_item else None
        if splitter is None or splitter.count() < 2:
            return

        vita_box = splitter.widget(1)
        if not isinstance(vita_box, QGroupBox):
            return

        vita_box.setTitle("PlayStation Vita")
        device_layout = vita_box.layout()
        if device_layout is None:
            return

        vita_storage_button = QPushButton("Manage SD / Local Storage")
        vita_storage_button.clicked.connect(self.open_vita_storage)
        insert_at = max(0, device_layout.count() - 4)
        device_layout.insertWidget(insert_at, vita_storage_button)

        three_ds_box = QGroupBox("Nintendo 3DS")
        three_ds_layout = QVBoxLayout(three_ds_box)
        self.three_ds_status = QLabel()
        self.three_ds_endpoint = QLabel()
        self.three_ds_endpoint.setTextInteractionFlags(Qt.TextSelectableByMouse)

        manage_button = QPushButton("Manage 3DS FTP")
        manage_button.clicked.connect(self.open_3ds)
        storage_button = QPushButton("Manage SD / Local Storage")
        storage_button.clicked.connect(self.open_3ds_storage)

        three_ds_layout.addWidget(self.three_ds_status)
        three_ds_layout.addWidget(self.three_ds_endpoint)
        three_ds_layout.addWidget(manage_button)
        three_ds_layout.addWidget(storage_button)
        three_ds_layout.addStretch()
        device_layout.addWidget(three_ds_box)

        self.refresh_device_sections()
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([850, 400])

    def refresh_device_sections(self) -> None:
        config = load_config()
        saved = config.get("devices", {}).get("3ds", {})
        host = str(saved.get("host", "")).strip()
        port = saved.get("port", 5000)
        self.three_ds_status.setText("Configured" if host else "Not configured")
        self.three_ds_endpoint.setText(
            f"FTP endpoint: {host}:{port}" if host else "FTP endpoint: not configured"
        )

    def open_3ds(self) -> None:
        if self._three_ds_dialog is None:
            self._three_ds_dialog = ThreeDSFtpDialog(self.config, self)
            self._three_ds_dialog.finished.connect(self._three_ds_closed)
        self._three_ds_dialog.show()
        self._three_ds_dialog.raise_()
        self._three_ds_dialog.activateWindow()

    def _three_ds_closed(self, _result: int) -> None:
        self._three_ds_dialog = None
        self.refresh_device_sections()

    def open_vita_storage(self) -> None:
        if self._vita_storage_dialog is None:
            self._vita_storage_dialog = MountedStorageDialog(
                self.config, "vita", "PlayStation Vita", self
            )
            self._vita_storage_dialog.finished.connect(self._vita_storage_closed)
        self._vita_storage_dialog.show()
        self._vita_storage_dialog.raise_()
        self._vita_storage_dialog.activateWindow()

    def _vita_storage_closed(self, _result: int) -> None:
        self._vita_storage_dialog = None

    def open_3ds_storage(self) -> None:
        if self._three_ds_storage_dialog is None:
            self._three_ds_storage_dialog = MountedStorageDialog(
                self.config, "3ds", "Nintendo 3DS", self
            )
            self._three_ds_storage_dialog.finished.connect(self._three_ds_storage_closed)
        self._three_ds_storage_dialog.show()
        self._three_ds_storage_dialog.raise_()
        self._three_ds_storage_dialog.activateWindow()

    def _three_ds_storage_closed(self, _result: int) -> None:
        self._three_ds_storage_dialog = None


def main() -> None:
    from PySide6.QtWidgets import QApplication, QDialog

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("RommHeld")
    app.setApplicationVersion("0.10")
    config = load_config()
    if not config.get("setup_complete"):
        from .ui import SetupWizard

        wizard = SetupWizard(config)
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return
        config = load_config()

    window = DeviceDashboardWindow(config)
    window.show()
    app.exec()
