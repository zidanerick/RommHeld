from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

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
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from .config import load_config
from .storage_validation import validate_storage
from .three_ds_ftp import ThreeDSFtpBackend, ThreeDSFtpSettings


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
    path = Path(__file__).resolve().parent.parent / ".rommheld_qr_tmp.png"
    image.save(path)
    pixmap = QPixmap(str(path))
    path.unlink(missing_ok=True)
    return pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


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
        ftp_buttons = QHBoxLayout()
        ftp_open = QPushButton("Open FTP Manager")
        ftp_open.clicked.connect(self.accept)
        ftp_buttons.addWidget(ftp_open)
        ftp_open.setToolTip("Open the 3DS FTP manager")
        ftp_layout.addRow("", ftp_buttons)

        component_box = QGroupBox("Homebrew Components")
        component_layout = QVBoxLayout(component_box)
        self.component_list = QListWidget()
        component_layout.addWidget(self.component_list)
        refresh_components = QPushButton("Refresh Detection")
        refresh_components.clicked.connect(self.refresh_components)
        component_layout.addWidget(refresh_components)

        action_box = QGroupBox("Install / Stage")
        action_layout = QVBoxLayout(action_box)
        action_layout.addWidget(QLabel(
            "RommHeld does not silently install software. Choose an upstream release, "
            "then stage the downloaded CIA/3DSX for manual FBI installation or create a QR "
            "code for FBI Remote Install."
        ))
        url_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("HTTPS URL to a CIA/3DSX/other supported package")
        stage_button = QPushButton("Stage URL")
        stage_button.clicked.connect(self.stage_url)
        qr_button = QPushButton("Show QR")
        qr_button.clicked.connect(self.show_qr)
        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(stage_button)
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

    def stage_url(self) -> None:
        url = self.url_edit.text().strip()
        if not is_web_url(url):
            QMessageBox.warning(self, "Invalid URL", "Enter a complete HTTPS or HTTP URL.")
            return
        QMessageBox.information(
            self,
            "Staging",
            "The upstream package URL has been accepted as a staging source. "
            "The actual download/staging action will be handled by the shared transfer/download service.",
        )

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
