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
    QComboBox,
)

from .platform_services import temp_dir
from .storage_detection import detect_3ds_sd_candidates
from .storage_validation import validate_3ds_sd


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
        "3DS title manager and installer. SD evidence can show a homebrew 3DSX or theme directory; an installed CIA title cannot be reliably inferred from SD files alone.",
        ("fbi/theme", "3ds/FBI/FBI.3dsx", "3ds/fbi/fbi.3dsx", "FBI.3dsx", "FBI.cia"),
        "https://github.com/Steveice10/FBI/releases",
    ),
    SetupComponent(
        "universal-updater",
        "Universal-Updater",
        "3DS homebrew updater and software catalogue.",
        ("3ds/Universal-Updater.3dsx", "3ds/Universal-Updater/Universal-Updater.3dsx", "Universal-Updater.cia"),
        "https://github.com/Universal-Team/Universal-Updater/releases",
    ),
    SetupComponent(
        "luma",
        "Luma3DS",
        "Custom firmware files detected from the SD root.",
        ("boot.firm", "luma/config.ini", "luma"),
        "https://github.com/LumaTeam/Luma3DS/releases",
    ),
    SetupComponent(
        "twilight",
        "TWiLight Menu++",
        "DS/DSi frontend and loader environment. The files can be present on the 3DS SD or a flashcard SD.",
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


def _case_insensitive_exists(root: Path, marker: str) -> bool:
    """Match common FAT-style paths without requiring exact directory casing."""
    current = root
    for part in Path(marker).parts:
        if current.is_dir():
            try:
                match = next((item for item in current.iterdir() if item.name.lower() == part.lower()), None)
            except OSError:
                return False
            if match is None:
                return False
            current = match
        else:
            return False
    return current.exists()


def component_presence(root: Path, component: SetupComponent) -> tuple[bool, str | None]:
    for marker in component.markers:
        if _case_insensitive_exists(root, marker):
            return True, marker
    return False, None


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
        self.resize(920, 760)

        self.root_edit = QLineEdit()
        self.root_edit.setPlaceholderText("Mounted 3DS SD-card root")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.choose_root)
        detect = QPushButton("Detect SD")
        detect.clicked.connect(self.detect_sd)
        root_row = QHBoxLayout()
        root_row.addWidget(self.root_edit, 1)
        root_row.addWidget(detect)
        root_row.addWidget(browse)

        root_form = QFormLayout()
        root_form.addRow("Local SD root:", root_row)
        self.validation_status = QLabel("No SD card selected.")
        self.validation_status.setWordWrap(True)
        root_form.addRow("Validation:", self.validation_status)

        validate_button = QPushButton("Validate selected SD")
        validate_button.clicked.connect(self.validate_sd)
        root_form.addRow("", validate_button)

        storage_box = QGroupBox("3DS Storage")
        storage_layout = QVBoxLayout(storage_box)
        storage_layout.addLayout(root_form)
        self.signature_list = QListWidget()
        self.signature_list.setMaximumHeight(150)
        storage_layout.addWidget(self.signature_list)
        self.candidate_combo = QComboBox()
        self.candidate_combo.currentIndexChanged.connect(self.use_candidate)
        storage_layout.addWidget(self.candidate_combo)
        self.candidate_note = QLabel("Automatic detection checks writable mounted volumes for 3DS-specific markers.")
        self.candidate_note.setWordWrap(True)
        storage_layout.addWidget(self.candidate_note)

        ftp_box = QGroupBox("FTP connection")
        ftp_layout = QFormLayout(ftp_box)
        saved = config.get("devices", {}).get("3ds", {})
        self.host_edit = QLineEdit(str(saved.get("host", "")))
        self.port_edit = QLineEdit(str(saved.get("port", 5000)))
        ftp_layout.addRow("Host:", self.host_edit)
        ftp_layout.addRow("Port:", self.port_edit)
        ftp_open = QPushButton("Open FTP Manager")
        ftp_open.clicked.connect(lambda: self.done(2))
        ftp_layout.addRow("", ftp_open)

        component_box = QGroupBox("Homebrew / Runtime SD Evidence")
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
            "then stage a downloaded CIA/3DSX for manual installation or create a QR "
            "code for FBI Remote Install."
        ))
        url_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("HTTPS URL to a CIA/3DSX/package")
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

        self.refresh_candidates()
        self.refresh_components()

    def choose_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose mounted 3DS SD-card root")
        if path:
            self.root_edit.setText(path)
            self.validate_sd()
            self.refresh_components()

    def detect_sd(self) -> None:
        candidates = detect_3ds_sd_candidates()
        self.candidate_combo.blockSignals(True)
        self.candidate_combo.clear()
        for candidate in candidates:
            label = candidate.label or candidate.root.name or str(candidate.root)
            self.candidate_combo.addItem(
                f"{label} — {candidate.root} — {candidate.validation.confidence} confidence",
                str(candidate.root),
            )
        self.candidate_combo.blockSignals(False)
        if candidates:
            self.candidate_combo.setCurrentIndex(0)
            self.use_candidate(0)
            self.candidate_note.setText(f"Found {len(candidates)} possible 3DS SD volume(s). Review confidence before using one.")
        else:
            self.candidate_note.setText("No writable volume with enough 3DS-specific evidence was detected. Select the SD root manually.")

    def refresh_candidates(self) -> None:
        self.detect_sd()

    def use_candidate(self, index: int) -> None:
        raw = self.candidate_combo.itemData(index)
        if raw:
            self.root_edit.setText(str(raw))
            self.validate_sd()
            self.refresh_components()

    def validate_sd(self) -> None:
        raw = self.root_edit.text().strip()
        if not raw:
            self.validation_status.setText("Choose or detect the mounted 3DS SD-card root first.")
            return
        try:
            result = validate_3ds_sd(Path(raw))
        except (OSError, ValueError) as exc:
            self.validation_status.setText(f"Validation failed: {exc}")
            return
        self.validation_status.setText(
            f"{result.kind} • confidence: {result.confidence} • {result.matched_count} markers matched"
        )
        self.signature_list.clear()
        for signature in result.signatures:
            self.signature_list.addItem(signature)

    def refresh_components(self) -> None:
        self.component_list.clear()
        root = Path(self.root_edit.text()).expanduser() if self.root_edit.text().strip() else None
        for component in COMPONENTS:
            present, marker = (
                component_presence(root, component) if root and root.is_dir() else (False, None)
            )
            state = f"SD evidence • {marker}" if present and marker else "No SD evidence"
            item = QListWidgetItem(f"{component.name}: {state}")
            item.setToolTip(
                component.description
                + " Installed title state is not inferred from SD evidence."
            )
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
