from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QPushButton, QVBoxLayout

from .app import MainWindow as BaseMainWindow, ThreeDSFtpDialog
from .config import load_config
from .vita import find_vita_mounts


class DeviceDashboardWindow(BaseMainWindow):
    """RommHeld main window with persistent per-device management cards."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._three_ds_dialog: ThreeDSFtpDialog | None = None
        self._replace_right_panel()

    def _replace_right_panel(self) -> None:
        central = self.centralWidget()
        if central is None:
            return
        layout = central.layout()
        if layout is None or layout.count() < 2:
            return
        splitter = layout.itemAt(1).widget()
        if splitter is None or splitter.count() < 2:
            return

        vita_box = splitter.widget(1)
        if vita_box is None:
            return

        devices_box = QGroupBox("Devices")
        devices_layout = QVBoxLayout(devices_box)
        splitter.replaceWidget(1, devices_box)
        devices_layout.addWidget(vita_box)

        three_ds_box = QGroupBox("Nintendo 3DS")
        three_ds_layout = QVBoxLayout(three_ds_box)
        self.three_ds_status = QLabel()
        self.three_ds_endpoint = QLabel()
        self.three_ds_endpoint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        manage_button = QPushButton("Manage 3DS FTP")
        manage_button.clicked.connect(self.open_3ds)

        three_ds_layout.addWidget(self.three_ds_status)
        three_ds_layout.addWidget(self.three_ds_endpoint)
        three_ds_layout.addWidget(manage_button)
        three_ds_layout.addStretch()
        devices_layout.addWidget(three_ds_box)

        self.refresh_device_cards()
        splitter.setSizes([850, 400])

    def refresh_device_cards(self) -> None:
        if not hasattr(self, "three_ds_status"):
            return

        config = load_config()
        saved = config.get("devices", {}).get("3ds", {})
        host = str(saved.get("host", "")).strip()
        port = saved.get("port", 5000)
        self.three_ds_status.setText("3DS: configured" if host else "3DS: not configured")
        self.three_ds_endpoint.setText(
            f"FTP endpoint: {host}:{port}" if host else "FTP endpoint: not configured"
        )

        mounts = find_vita_mounts()
        if not mounts:
            return

    def open_3ds(self) -> None:
        if self._three_ds_dialog is None:
            self._three_ds_dialog = ThreeDSFtpDialog(self.config, self)
            self._three_ds_dialog.finished.connect(self._three_ds_closed)
        self._three_ds_dialog.show()
        self._three_ds_dialog.raise_()
        self._three_ds_dialog.activateWindow()

    def _three_ds_closed(self, _result: int) -> None:
        self._three_ds_dialog = None
        self.refresh_device_cards()


def main() -> None:
    from PySide6.QtWidgets import QApplication, QDialog

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("RommHeld")
    app.setApplicationVersion("0.9")
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
