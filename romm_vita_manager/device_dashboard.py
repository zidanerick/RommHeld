from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .app import MainWindow as BaseMainWindow, ThreeDSFtpDialog
from .config import load_config, save_config
from .preferences import get_device_preference, preference_options, set_device_preference
from .vita import find_vita_mounts, free_space

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


class DeviceDashboardWindow(BaseMainWindow):
    """RommHeld main window with persistent per-device management sections."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.setWindowTitle("RommHeld")
        self._three_ds_dialog: ThreeDSFtpDialog | None = None
        self._build_status_bar()
        self._build_device_sections()
        self.refresh_device_sections()

    def _build_device_sections(self) -> None:
        central = self.centralWidget()
        if central is None or central.layout() is None:
            return
        layout = central.layout()
        splitter_item = next(
            (
                layout.itemAt(i)
                for i in range(layout.count())
                if layout.itemAt(i).widget() is not None
                and hasattr(layout.itemAt(i).widget(), "count")
            ),
            None,
        )
        splitter = splitter_item.widget() if splitter_item else None
        if splitter is None or splitter.count() < 2:
            return
        vita_box = splitter.widget(1)
        if not isinstance(vita_box, QGroupBox):
            return

        vita_box.setTitle("Devices")
        vita_box.setObjectName("devicesPanel")
        device_layout = vita_box.layout()
        if device_layout is None:
            return

        vita_heading = QLabel("PlayStation Vita")
        vita_heading.setObjectName("vitaHeading")
        vita_heading.setToolTip("USB / VitaShell device management")
        device_layout.insertWidget(0, vita_heading)
        device_layout.insertWidget(1, self._build_preference_box("vita", "Vita runtime priority"))

        three_ds_box = QGroupBox("Nintendo 3DS")
        three_ds_box.setObjectName("threeDsCard")
        three_ds_layout = QVBoxLayout(three_ds_box)
        self.three_ds_status = QLabel()
        self.three_ds_endpoint = QLabel()
        self.three_ds_endpoint.setTextInteractionFlags(Qt.TextSelectableByMouse)

        three_ds_layout.addWidget(self.three_ds_status)
        three_ds_layout.addWidget(self.three_ds_endpoint)
        three_ds_layout.addWidget(self._build_preference_box("3ds", "3DS runtime priority"))
        manage_button = QPushButton("Manage 3DS FTP")
        manage_button.clicked.connect(self.open_3ds)
        three_ds_layout.addWidget(manage_button)
        three_ds_layout.addStretch()
        device_layout.addWidget(three_ds_box)

        vita_box.setStyleSheet(
            """
            QGroupBox#devicesPanel { border: 1px solid #3c67d6; border-radius: 10px; margin-top: 8px; padding-top: 8px; }
            QGroupBox#devicesPanel::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #3c67d6; font-weight: 700; }
            QLabel#vitaHeading { color: #3157b7; font-size: 16px; font-weight: 700; padding: 3px 2px 8px 2px; }
            QGroupBox#threeDsCard { border: 1px solid #d93636; border-radius: 10px; margin-top: 10px; padding-top: 8px; }
            QGroupBox#threeDsCard::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #c72d2d; font-weight: 700; }
            QGroupBox#threeDsCard QPushButton { min-height: 30px; }
            """
        )
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([850, 400])

    def _build_preference_box(self, device_key: str, title: str) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 6, 8, 6)
        selected = get_device_preference(self.config, device_key)
        for option in preference_options():
            radio = QRadioButton(option.label)
            radio.setProperty("preference_key", option.key)
            radio.setProperty("device_key", device_key)
            radio.setChecked(selected == option.key)
            radio.toggled.connect(self._runtime_preference_changed)
            layout.addWidget(radio)
        return box

    def _runtime_preference_changed(self, checked: bool) -> None:
        if not checked:
            return
        radio = self.sender()
        if not isinstance(radio, QRadioButton):
            return
        device_key = str(radio.property("device_key"))
        preference = str(radio.property("preference_key"))
        try:
            updated = set_device_preference(load_config(), device_key, preference)
            save_config(updated)
            self.config = updated
        except (TypeError, ValueError, OSError):
            pass

    def _build_status_bar(self) -> None:
        status_bar = QStatusBar(self)
        status_bar.setSizeGripEnabled(False)
        self.setStatusBar(status_bar)
        self.vita_status_widget = self._make_status_widget("vita.svg", "Vita", "Not detected")
        self.three_ds_status_widget = self._make_status_widget("3ds.svg", "3DS", "Not configured")
        status_bar.addPermanentWidget(self.vita_status_widget)
        status_bar.addPermanentWidget(self.three_ds_status_widget)

    def _make_status_widget(self, icon_name: str, label: str, text: str) -> QWidget:
        container = QWidget(self)
        row = QHBoxLayout(container)
        row.setContentsMargins(4, 0, 4, 0)
        row.setSpacing(5)
        icon = QLabel()
        icon_path = ASSET_DIR / icon_name
        if icon_path.is_file():
            icon.setPixmap(QIcon(str(icon_path)).pixmap(20, 20))
        row.addWidget(icon)
        value = QLabel(f"{label}: {text}")
        row.addWidget(value)
        row.addStretch()
        container.setMinimumWidth(190)
        container.setToolTip(f"{label} device status")
        return container

    @staticmethod
    def _set_status_text(container: QWidget, text: str) -> None:
        labels = container.findChildren(QLabel)
        if labels:
            labels[-1].setText(text)

    def refresh_status_bar(self) -> None:
        mounts = find_vita_mounts()
        if mounts:
            try:
                free = free_space(mounts[0])
                vita_text = f"Connected • {self._human_size(free)} free"
            except OSError:
                vita_text = "Connected"
        else:
            vita_text = "Not detected"
        config = load_config()
        saved = config.get("devices", {}).get("3ds", {})
        host = str(saved.get("host", "")).strip()
        port = saved.get("port", 5000)
        three_ds_text = f"FTP {host}:{port}" if host else "Not configured"
        self._set_status_text(self.vita_status_widget, f"Vita: {vita_text}")
        self._set_status_text(self.three_ds_status_widget, f"3DS: {three_ds_text}")

    @staticmethod
    def _human_size(value: int) -> str:
        n = float(value)
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if n < 1024 or unit == "TiB":
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{value} B"

    def refresh_device_sections(self) -> None:
        config = load_config()
        saved = config.get("devices", {}).get("3ds", {})
        host = str(saved.get("host", "")).strip()
        port = saved.get("port", 5000)
        self.three_ds_status.setText("Configured" if host else "Not configured")
        self.three_ds_endpoint.setText(
            f"FTP endpoint: {host}:{port}" if host else "FTP endpoint: not configured"
        )
        self.refresh_status_bar()

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
