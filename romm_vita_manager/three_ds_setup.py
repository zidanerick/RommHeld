from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
import tempfile
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .config import save_config
from .design_tokens import DARK, brand_for_platform
from .platform_services import temp_dir
from .storage_detection import detect_3ds_sd_candidates
from .storage_validation import validate_3ds_sd
from .three_ds_readiness_ui import ThreeDSReadinessDialog
from .ui_components import AccentButton, SectionHeader, StatusPill, SurfaceCard


NINTENDO_RED = brand_for_platform("3ds").accent
FTPD_RELEASE_URL = "https://github.com/mtheall/ftpd/releases"


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
    """Guided 3DS setup surface that keeps storage, FTP and FBI distinct."""

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Nintendo 3DS Setup")
        self.resize(960, 780)
        self.setMinimumSize(820, 660)

        saved = config.get("devices", {}).get("3ds", {})
        self._ftp_host = str(saved.get("host", "")).strip()
        self._ftp_port = saved.get("port", 5000)
        saved_storage_root = str(saved.get("storage_root", "")).strip()

        self.root_edit = QLineEdit(saved_storage_root)
        self.root_edit.setPlaceholderText("Mounted Nintendo 3DS SD-card root")
        self.root_edit.textChanged.connect(self._storage_selection_changed)

        self.validation_status = QLabel("Choose or detect the mounted 3DS SD card.")
        self.validation_status.setWordWrap(True)
        self.validation_status.setProperty("secondary", True)

        self.signature_list = QListWidget()
        self.signature_list.setMaximumHeight(110)
        self.signature_list.setVisible(False)

        self.candidate_combo = QComboBox()
        self.candidate_combo.setMinimumWidth(320)
        self.candidate_combo.currentIndexChanged.connect(self.use_candidate)
        self.candidate_note = QLabel(
            "Automatic detection checks writable mounted volumes for 3DS-specific markers."
        )
        self.candidate_note.setWordWrap(True)
        self.candidate_note.setProperty("secondary", True)

        self.sd_status = StatusPill(
            "SD card", "Not validated" if saved_storage_root else "Not selected"
        )
        self.ftp_status = StatusPill(
            "FTP", "Configured" if self._ftp_host else "Needs setup"
        )
        self.fbi_status = StatusPill("FBI", "Not checked")

        header = SectionHeader(
            "Prepare your Nintendo 3DS",
            "Validate a mounted SD card for direct/offline file access, configure ftpd for live-console transfers, then confirm FBI separately if you want Remote Install.",
        )
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        status_row.addWidget(self.sd_status)
        status_row.addWidget(self.ftp_status)
        status_row.addWidget(self.fbi_status)
        status_row.addStretch(1)

        storage_card = SurfaceCard()
        storage_card.content.addWidget(self._card_title("1 · Validate the SD card"))
        storage_card.content.addWidget(
            self._secondary(
                "Use the SD or microSD card mounted through a card reader when you want direct filesystem access. RommHeld remembers only a medium or high-confidence 3DS root and will not write to an unrecognised directory."
            )
        )

        detect_row = QHBoxLayout()
        detect_row.setSpacing(8)
        detect_row.addWidget(self.candidate_combo, 1)
        detect = QPushButton("Detect SD")
        detect.clicked.connect(self.detect_sd)
        detect_row.addWidget(detect)
        storage_card.content.addLayout(detect_row)

        root_row = QHBoxLayout()
        root_row.setSpacing(8)
        root_row.addWidget(self.root_edit, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.choose_root)
        validate_button = AccentButton("Validate", NINTENDO_RED)
        validate_button.clicked.connect(self.validate_sd)
        root_row.addWidget(browse)
        root_row.addWidget(validate_button)
        storage_card.content.addLayout(root_row)
        storage_card.content.addWidget(self.validation_status)
        storage_card.content.addWidget(self.signature_list)
        storage_card.content.addWidget(self.candidate_note)

        ftp_card = SurfaceCard()
        ftp_card.content.addWidget(self._card_title("2 · Configure FTP file transfer"))
        ftp_card.content.addWidget(
            self._secondary(
                "FTP is the wireless live-console filesystem transport. It is separate from mounted-SD access and a working FTP connection does not imply that FBI is installed or ready for Remote Install."
            )
        )
        ftp_card.content.addWidget(
            self._secondary(
                "Recommended server: mtheall ftpd. Open ftpd on the 3DS and leave it running, then enter the IP address and port shown on its screen. Port 5000 is the normal default; username and password are only needed if you configured authentication in ftpd."
            )
        )
        ftp_row = QHBoxLayout()
        ftp_row.setSpacing(10)
        endpoint = QLabel(self._ftp_endpoint_text())
        endpoint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        endpoint.setStyleSheet(
            f"color:{DARK.text_primary};font-weight:600;background:transparent;"
        )
        ftp_row.addWidget(endpoint, 1)
        ftp_release = QPushButton("Open ftpd release")
        ftp_release.clicked.connect(self.open_ftpd_upstream)
        ftp_open = AccentButton(
            "Open FTP Manager" if self._ftp_host else "Configure FTP",
            NINTENDO_RED,
        )
        ftp_open.clicked.connect(lambda: self.done(2))
        ftp_row.addWidget(ftp_release)
        ftp_row.addWidget(ftp_open)
        ftp_card.content.addLayout(ftp_row)

        fbi_card = SurfaceCard()
        fbi_card.content.addWidget(self._card_title("3 · Confirm FBI Remote Install readiness"))
        fbi_card.content.addWidget(
            self._secondary(
                "RommHeld can detect some FBI-related files on the SD card, but it cannot reliably prove that the FBI CIA title is installed. Treat SD evidence as a hint, then verify FBI on the console."
            )
        )
        self.fbi_evidence = QLabel("Validate an SD card to check for FBI-related files.")
        self.fbi_evidence.setWordWrap(True)
        self.fbi_evidence.setStyleSheet(
            f"color:{DARK.text_primary};font-weight:600;background:transparent;"
        )
        fbi_card.content.addWidget(self.fbi_evidence)

        fbi_actions = QHBoxLayout()
        fbi_actions.setSpacing(8)
        refresh_fbi = QPushButton("Recheck SD evidence")
        refresh_fbi.clicked.connect(self.refresh_components)
        fbi_release = QPushButton("Open FBI release")
        fbi_release.clicked.connect(self.open_fbi_upstream)
        fbi_actions.addWidget(refresh_fbi)
        fbi_actions.addWidget(fbi_release)
        fbi_actions.addStretch(1)
        fbi_card.content.addLayout(fbi_actions)

        qr_note = self._secondary(
            "When FBI is open on the 3DS, paste a direct HTTP(S) package URL here to create a Remote Install QR code."
        )
        fbi_card.content.addWidget(qr_note)
        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://example.com/package.cia")
        qr_button = QPushButton("Show install QR")
        qr_button.clicked.connect(self.show_qr)
        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(qr_button)
        fbi_card.content.addLayout(url_row)

        runtime_card = SurfaceCard()
        runtime_card.content.addWidget(self._card_title("Runtime and homebrew checks"))
        runtime_card.content.addWidget(
            self._secondary(
                "The quick list below shows common SD-side signals. Open Readiness & Runtimes for required/recommended status, dedicated emulator checks, safe 3DSX staging, and supported runtime configuration."
            )
        )
        self.component_list = QListWidget()
        self.component_list.setMaximumHeight(155)
        runtime_card.content.addWidget(self.component_list)
        component_buttons = QHBoxLayout()
        component_buttons.setSpacing(8)
        refresh_components = QPushButton("Refresh checks")
        refresh_components.clicked.connect(self.refresh_components)
        upstream_button = QPushButton("Open selected release")
        upstream_button.clicked.connect(self.open_upstream)
        manage_runtimes = AccentButton("Readiness & Runtimes", NINTENDO_RED)
        manage_runtimes.clicked.connect(self.open_readiness)
        component_buttons.addWidget(refresh_components)
        component_buttons.addWidget(upstream_button)
        component_buttons.addStretch(1)
        component_buttons.addWidget(manage_runtimes)
        runtime_card.content.addLayout(component_buttons)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close = QPushButton("Done")
        close.clicked.connect(self.accept)
        close_row.addWidget(close)

        scroll_body = QWidget()
        scroll_body_layout = QVBoxLayout(scroll_body)
        scroll_body_layout.setContentsMargins(0, 0, 0, 0)
        scroll_body_layout.setSpacing(12)
        scroll_body_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        scroll_body_layout.addWidget(storage_card)
        scroll_body_layout.addWidget(ftp_card)
        scroll_body_layout.addWidget(fbi_card)
        scroll_body_layout.addWidget(runtime_card)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(scroll_body)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(header)
        layout.addLayout(status_row)
        layout.addWidget(scroll, 1)
        layout.addLayout(close_row)

        self.refresh_candidates()
        if saved_storage_root:
            self.validate_sd()
        self.refresh_components()

    def _card_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"color:{DARK.text_primary};font-size:15px;font-weight:700;background:transparent;"
        )
        return label

    def _secondary(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{DARK.text_secondary};background:transparent;")
        return label

    def _ftp_endpoint_text(self) -> str:
        if not self._ftp_host:
            return "No FTP endpoint configured yet"
        return f"ftp://{self._ftp_host}:{self._ftp_port}"

    def _storage_selection_changed(self) -> None:
        if self.root_edit.text().strip():
            self.sd_status.set_value("Not validated")
        else:
            self.sd_status.set_value("Not selected")
        self.fbi_status.set_value("Not checked")
        self.fbi_evidence.setText("Validate an SD card to check for FBI-related files.")

    def choose_root(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Choose mounted 3DS SD-card root",
            self.root_edit.text().strip(),
        )
        if path:
            self.root_edit.setText(path)
            self.validate_sd()
            self.refresh_components()

    def detect_sd(self) -> None:
        selected_path = self.root_edit.text().strip()
        candidates = detect_3ds_sd_candidates()
        self.candidate_combo.blockSignals(True)
        self.candidate_combo.clear()
        for candidate in candidates:
            label = candidate.label or candidate.root.name or str(candidate.root)
            self.candidate_combo.addItem(
                f"{label} — {candidate.root} — {candidate.validation.confidence} confidence",
                str(candidate.root),
            )
        if candidates:
            match = self.candidate_combo.findData(selected_path) if selected_path else -1
            self.candidate_combo.setCurrentIndex(match if match >= 0 else 0)
        self.candidate_combo.blockSignals(False)
        if candidates:
            if not selected_path:
                self.use_candidate(self.candidate_combo.currentIndex())
            self.candidate_note.setText(
                f"Found {len(candidates)} possible 3DS SD volume(s). Review the validation confidence before using one."
            )
        else:
            self.candidate_note.setText(
                "No writable volume with enough 3DS-specific evidence was detected. Select the SD root manually."
            )

    def refresh_candidates(self) -> None:
        self.detect_sd()

    def use_candidate(self, index: int) -> None:
        raw = self.candidate_combo.itemData(index)
        if raw:
            self.root_edit.setText(str(raw))
            self.validate_sd()
            self.refresh_components()

    def _save_storage_root(self, root: Path) -> None:
        cfg = dict(self.config)
        devices = dict(cfg.get("devices", {}))
        device = dict(devices.get("3ds", {}))
        device["storage_root"] = str(root.resolve())
        devices["3ds"] = device
        cfg["devices"] = devices
        save_config(cfg)
        self.config = cfg

    def validate_sd(self) -> None:
        raw = self.root_edit.text().strip()
        self.signature_list.clear()
        self.signature_list.setVisible(False)
        if not raw:
            self.sd_status.set_value("Not selected")
            self.validation_status.setText("Choose or detect the mounted 3DS SD-card root first.")
            return
        try:
            root = Path(raw).expanduser()
            result = validate_3ds_sd(root)
        except (OSError, ValueError) as exc:
            self.sd_status.set_value("Validation failed")
            self.validation_status.setText(f"Validation failed: {exc}")
            return
        self.sd_status.set_value(result.confidence.capitalize())
        suffix = ""
        if result.confidence in {"medium", "high"}:
            self._save_storage_root(root)
            suffix = " · saved for direct SD transfers"
        else:
            suffix = " · not saved for writes"
        self.validation_status.setText(
            f"{result.kind} • {result.confidence} confidence • {result.matched_count} markers matched{suffix}"
        )
        for signature in result.signatures:
            self.signature_list.addItem(signature)
        self.signature_list.setVisible(bool(result.signatures))
        self.refresh_components()

    def refresh_components(self) -> None:
        self.component_list.clear()
        root = Path(self.root_edit.text()).expanduser() if self.root_edit.text().strip() else None

        fbi = COMPONENTS[0]
        fbi_present, fbi_marker = (
            component_presence(root, fbi) if root and root.is_dir() else (False, None)
        )
        if not root or not root.is_dir():
            self.fbi_status.set_value("Not checked")
            self.fbi_evidence.setText("Validate an SD card to check for FBI-related files.")
        elif fbi_present and fbi_marker:
            self.fbi_status.set_value("SD evidence found")
            self.fbi_evidence.setText(
                f"Found SD evidence at {fbi_marker}. This supports FBI readiness, but verify the installed title on the console before relying on Remote Install."
            )
        else:
            self.fbi_status.set_value("Not confirmed")
            self.fbi_evidence.setText(
                "No FBI-related SD evidence was found. FBI may still be installed as a title, so check the 3DS Home Menu before treating it as unavailable."
            )

        for component in COMPONENTS[1:]:
            present, marker = (
                component_presence(root, component) if root and root.is_dir() else (False, None)
            )
            state = f"Detected • {marker}" if present and marker else "No SD evidence"
            item = QListWidgetItem(f"{component.name} — {state}")
            item.setToolTip(component.description)
            item.setData(Qt.ItemDataRole.UserRole, component.upstream_url)
            self.component_list.addItem(item)

    def open_readiness(self) -> None:
        raw = self.root_edit.text().strip()
        if not raw:
            QMessageBox.information(
                self,
                "Select the 3DS SD card",
                "Choose or detect the mounted Nintendo 3DS SD-card root first.",
            )
            return
        root = Path(raw).expanduser()
        try:
            validation = validate_3ds_sd(root)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "3DS SD card unavailable", str(exc))
            return
        if validation.confidence not in {"medium", "high"}:
            QMessageBox.warning(
                self,
                "3DS SD card not recognised",
                "Validate a medium or high-confidence Nintendo 3DS SD-card root before opening runtime readiness.",
            )
            return
        self._save_storage_root(root)
        ThreeDSReadinessDialog(root.resolve(), needs_ftp=True, parent=self).exec()
        self.validate_sd()
        self.refresh_components()

    def open_ftpd_upstream(self) -> None:
        if is_web_url(FTPD_RELEASE_URL):
            webbrowser.open(FTPD_RELEASE_URL)

    def open_fbi_upstream(self) -> None:
        url = COMPONENTS[0].upstream_url
        if is_web_url(url):
            webbrowser.open(url)

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
