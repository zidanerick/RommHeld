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

WORKSPACES = {
    "vita": {"name": "PlayStation Vita", "accent": "#4ca8ff", "icon": "vita.svg"},
    "3ds": {"name": "Nintendo 3DS", "accent": "#ef3b3b", "icon": "3ds.svg"},
    "ds": {"name": "Nintendo DS", "accent": "#63c2ff", "icon": "ds.svg"},
}


class DeviceDashboardWindow(BaseMainWindow):
    """RommHeld management workspace with persistent device management sections."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.setWindowTitle("RommHeld")
        self._three_ds_dialog: ThreeDSFtpDialog | None = None
        self._next_workspace_window: DeviceDashboardWindow | None = None
        self.workspace_key = str(config.get("active_console", "vita"))
        if self.workspace_key not in WORKSPACES:
            self.workspace_key = "vita"
        self._build_status_bar()
        self._build_device_sections()
        self._apply_workspace_theme()
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

        self.workspace_banner = QWidget()
        banner_layout = QHBoxLayout(self.workspace_banner)
        banner_layout.setContentsMargins(2, 2, 2, 6)
        banner_layout.setSpacing(8)
        self.workspace_icon = QLabel()
        self.workspace_icon.setFixedSize(28, 28)
        banner_layout.addWidget(self.workspace_icon)
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)
        self.workspace_heading = QLabel()
        self.workspace_heading.setObjectName("workspaceHeading")
        self.workspace_subtitle = QLabel("Current workspace")
        self.workspace_subtitle.setObjectName("workspaceSubtitle")
        text_layout.addWidget(self.workspace_heading)
        text_layout.addWidget(self.workspace_subtitle)
        banner_layout.addLayout(text_layout, 1)
        change_button = QPushButton("Change handheld")
        change_button.clicked.connect(self.change_workspace)
        banner_layout.addWidget(change_button)
        device_layout.insertWidget(0, self.workspace_banner)

        vita_heading = QLabel("PlayStation Vita")
        vita_heading.setObjectName("vitaHeading")
        vita_heading.setToolTip("USB / VitaShell device management")
        device_layout.insertWidget(1, vita_heading)
        device_layout.insertWidget(2, self._build_preference_box("vita", "Vita runtime priority"))

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
        device_layout.addStretch()
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([850, 400])

    def _apply_workspace_theme(self) -> None:
        profile = WORKSPACES[self.workspace_key]
        self.setWindowTitle(f"RommHeld • {profile['name']}")
        icon_path = ASSET_DIR / profile["icon"]
        if icon_path.is_file():
            self.workspace_icon.setPixmap(QIcon(str(icon_path)).pixmap(28, 28))
        self.workspace_heading.setText(profile["name"])
        self.setStyleSheet(
            f"""
            QGroupBox#devicesPanel {{ border: 1px solid {profile['accent']}; border-radius: 12px; margin-top: 8px; padding-top: 8px; }}
            QGroupBox#devicesPanel::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {profile['accent']}; font-weight: 700; }}
            QLabel#workspaceHeading {{ color: {profile['accent']}; font-size: 18px; font-weight: 800; padding: 0; }}
            QLabel#workspaceSubtitle {{ color: #8d97a5; font-size: 10px; }}
            QLabel#vitaHeading {{ color: #86bfff; font-size: 15px; font-weight: 700; padding: 3px 2px 8px 2px; }}
            QGroupBox#threeDsCard {{ border: 1px solid #d93636; border-radius: 10px; margin-top: 10px; padding-top: 8px; }}
            QGroupBox#threeDsCard::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #e04444; font-weight: 700; }}
            QGroupBox#threeDsCard QPushButton {{ min-height: 30px; }}
            """
        )

    def change_workspace(self) -> None:
        from .platform_selector import PlatformSelectorDialog

        dialog = PlatformSelectorDialog(load_config(), self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        config = load_config()
        self._next_workspace_window = DeviceDashboardWindow(config)
        self._next_workspace_window.show()
        self.hide()

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
