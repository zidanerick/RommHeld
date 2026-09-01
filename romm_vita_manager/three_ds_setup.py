from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
import tempfile
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from .storage_validation import validate_storage
from .platform_services import temp_dir


@dataclass(frozen=True)
class SetupComponent:
    key: str
    name: str
    description: str
    markers: tuple[str, ...]
    upstream_url: str


COMPONENTS = (
    SetupComponent(
        "fbi",
        "FBI",
        "CIA/title manager and installer.",
        ("fbi/theme", "FBI.cia", "fbi.3dsx"),
        "https://github.com/Steveice10/FBI/releases",
    ),
    SetupComponent(
        "universal-updater",
        "Universal-Updater",
        "3DS homebrew updater and software catalogue.",
        ("3ds/Universal-Updater.3dsx", "Universal-Updater.cia"),
        "https://github.com/Universal-Team/Universal-Updater/releases",
    ),
    SetupComponent(
        "luma",
        "Luma3DS",
        "Custom firmware environment detected from the SD root.",
        ("boot.firm", "luma/config.ini"),
        "https://github.com/LumaTeam/Luma3DS/releases",
    ),
    SetupComponent(
        "twilight",
        "TWiLight Menu++",
        "Native DS/DSi frontend and loader environment.",
        ("_nds/TWiLightMenu", "_nds/nds-bootstrap"),
        "https://github.com/DS-Homebrew/TWiLightMenu/releases",
    ),
    SetupComponent(
        "open-agb-firm",
        "open_agb_firm",
        "Native GBA runtime for the 3DS.",
        ("luma/payloads/open_agb_firm.firm",),
        "https://github.com/profi200/open_agb_firm/releases",
    ),
)


def component_presence(root: Path, component: SetupComponent) -> bool:
    return any((root / marker).exists() for marker in component.markers)


def is_web_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def qr_image(url: str, size: int = 320) -> QPixmap:
    try:
        import qrcode
    except ImportError as exc:
        raise RuntimeError("Python package 'qrcode' is required for QR display.") from exc

    image = qrcode.make(url)
    temp_root = temp_dir()
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        suffix=".png", prefix="rommheld-qr-", dir=temp_root, delete=False
    ) as handle:
        path = Path(handle.name)
    try:
        image.save(path)
        pixmap = QPixmap(str(path))
    finally:
        path.unlink(missing_ok=True)
    return pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


class ThreeDSSetupDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Nintendo 3DS Setup")
        self.resize(900, 720)

        self.root_edit = QLineEdit()
        self.root_edit.setPlaceholderText("Optional: mounted 3DS SD-card root")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.choose_root)
        root_row = QHBoxLayout()
        root_row.addWidget(self.root_edit, 1)
        root_row.addWidget(browse)

        root_form = QFormLayout()
        root_form.addRow("Local SD root:", root_row)
        self.validation_status = QLabel("Select a mounted SD card to validate it.")
        root_form.addRow("Validation:", self.validation_status)

        validate_button = QPushButton("Validate SD Card")
        validate_button.clicked.connect(self.validate_sd)
        root_form.addRow("", validate_button)

        storage_box = QGroupBox("3DS Storage")
        storage_layout = QVBoxLayout(storage_box)
        storage_layout.addLayout(root_form)
        self.signature_list = QListWidget()
        self.signature_list.setMaximumHeight(130)
        storage_layout.addWidget(self.signature_list)

        ftp_box = QGroupBox("FTP")
        ftp_layout = QFormLayout(ftp_box)
        saved = config.get("devices", {}).get("3ds", {})
        self.host_edit = QLineEdit(str(saved.get("host", "")))
        self.port_edit = QLineEdit(str(saved.get("port", 5000)))
        ftp_layout.addRow("Host:", self.host_edit)
        ftp_layout.addRow("Port:", self.port_edit)
        ftp_open = QPushButton("Open FTP Manager")
        ftp_open.clicked.connect(lambda: self.done(2))
        ftp_layout.addRow("", ftp_open)

        component_box = QGroupBox("Homebrew Components")
        component_layout = QVBoxLayout(component_box)
        self.component_list = QListWidget()
        component_layout.addWidget(self.component_list)
        component_buttons = QHBoxLayout()
        refresh_components = QPushButton("Refresh Detection")
        refresh_components.clicked.connect(self.refresh_components)
        upstream_button = QPushButton("Open Upstream Release")
        upstream_button.clicked.connect(self.open_upstream)
        component_buttons.addWidget(refresh_components)
        component_buttons.addWidget(upstream_button)
        component_layout.addLayout(component_buttons)

        action_box = QGroupBox("Install / Stage")
        action_layout = QVBoxLayout(action_box)
        action_layout.addWidget(QLabel(
            "RommHeld does not silently install software. Choose an upstream release, "
            "then stage the downloaded CIA/3DSX for manual installation or create a QR "
            "code for FBI Remote Install."
        ))
        url_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("HTTPS URL to a CIA/3DSX/other supported package")
        qr_button = QPushButton("Show QR")
        qr_button.clicked.connect(self.show_qr)
        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(qr_button)
        action_layout.addLayout(url_row)

        layout = QVBoxLayout(self)
        layout.addWidget(storage_box)
        layout.addWidget(ftp_box)
        layout.addWidget(component_box, 1)
        layout.addWidget(action_box)

        self.refresh_components()

    def choose_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose mounted 3DS SD-card root")
        if path:
            self.root_edit.setText(path)
            self.refresh_components()

    def validate_sd(self) -> None:
        raw = self.root_edit.text().strip()
        if not raw:
            QMessageBox.warning(self, "No SD card selected", "Choose the mounted 3DS SD-card root first.")
            return
        try:
            result = validate_storage(Path(raw))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Storage validation failed", str(exc))
            return
        self.validation_status.setText(f"{result.kind} • confidence: {result.confidence}")
        self.signature_list.clear()
        for signature in result.signatures:
            self.signature_list.addItem(signature)

    def refresh_components(self) -> None:
        self.component_list.clear()
        root = Path(self.root_edit.text()).expanduser() if self.root_edit.text().strip() else None
        for component in COMPONENTS:
            present = bool(root and root.is_dir() and component_presence(root, component))
            state = "Installed / detected" if present else "Not detected"
            item = QListWidgetItem(f"{component.name}: {state}")
            item.setToolTip(component.description)
            item.setData(Qt.ItemDataRole.UserRole, component.upstream_url)
            self.component_list.addItem(item)

    def open_upstream(self) -> None:
        item = self.component_list.currentItem()
        if item is None:
            QMessageBox.information(self, "Select a component", "Select a component first.")
            return
        url = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if not is_web_url(url):
            QMessageBox.warning(self, "Invalid upstream URL", "The selected component has no valid upstream URL.")
            return
        webbrowser.open(url)

    def show_qr(self) -> None:
        url = self.url_edit.text().strip()
        if not is_web_url(url):
            QMessageBox.warning(self, "Invalid URL", "Enter a complete HTTPS or HTTP URL.")
            return
        try:
            pixmap = qr_image(url)
        except RuntimeError as exc:
            QMessageBox.warning(self, "QR unavailable", str(exc))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("FBI Remote Install QR")
        layout = QVBoxLayout(dialog)
        image = QLabel()
        image.setPixmap(pixmap)
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(image)
        text = QLabel(url)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(text)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()
