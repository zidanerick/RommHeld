from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from .design_tokens import brand_for_platform
from .open_agb_config import (
    detect_open_agb_config_format,
    open_agb_config_path,
    parse_open_agb_values,
    write_open_agb_config,
)
from .ui_components import AccentButton, SectionHeader, SurfaceCard


NINTENDO_RED = brand_for_platform("3ds").accent
SCALERS = (
    ("none", "Pixel perfect / no scaler"),
    ("bilinear", "Bilinear"),
    ("matrix", "Matrix"),
)
COLOR_PROFILES = (
    ("none", "None"),
    ("gba", "Game Boy Advance"),
    ("gb_micro", "Game Boy Micro"),
    ("gba_sp101", "GBA SP AGS-101"),
    ("nds", "Nintendo DS"),
    ("ds_lite", "Nintendo DS Lite"),
    ("nso", "Nintendo Switch Online style"),
    ("vba", "VisualBoyAdvance style"),
    ("identity", "Identity"),
)
AUDIO_OUTPUTS = (
    ("auto", "Automatic"),
    ("speakers", "Speakers"),
    ("headphones", "Headphones"),
)


class OpenAgbSettingsDialog(QDialog):
    """Edit a conservative subset of the current open_agb_firm config.ini."""

    def __init__(self, sd_root: Path, parent=None):
        super().__init__(parent)
        self.sd_root = sd_root.expanduser()
        self.config_path = open_agb_config_path(self.sd_root)
        self.setWindowTitle("open_agb_firm Settings")
        self.resize(620, 560)
        self.setMinimumWidth(560)

        header = SectionHeader(
            "open_agb_firm settings",
            "RommHeld edits only documented current-format settings. Existing comments and unknown keys are preserved, and the original file is backed up before the first change.",
        )

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setProperty("secondary", True)

        self.direct_boot = QCheckBox("Direct boot")
        self.use_saves_folder = QCheckBox("Keep saves in the saves folder")

        self.backlight = QSpinBox()
        self.backlight.setRange(16, 142)
        self.backlight.setToolTip(
            "open_agb_firm supports 16 to 142 overall; the console model may have a narrower practical range."
        )

        self.scaler = QComboBox()
        for key, label in SCALERS:
            self.scaler.addItem(label, key)

        self.color_profile = QComboBox()
        for key, label in COLOR_PROFILES:
            self.color_profile.addItem(label, key)

        self.audio_output = QComboBox()
        for key, label in AUDIO_OUTPUTS:
            self.audio_output.addItem(label, key)

        self.volume = QSpinBox()
        self.volume.setRange(-128, 127)

        general_card = SurfaceCard()
        general_form = QFormLayout()
        general_form.setContentsMargins(0, 0, 0, 0)
        general_form.setHorizontalSpacing(16)
        general_form.setVerticalSpacing(10)
        general_form.addRow("Launch behavior", self.direct_boot)
        general_form.addRow("Save layout", self.use_saves_folder)
        general_form.addRow("Backlight", self.backlight)
        general_card.content.addLayout(general_form)

        display_card = SurfaceCard()
        display_form = QFormLayout()
        display_form.setContentsMargins(0, 0, 0, 0)
        display_form.setHorizontalSpacing(16)
        display_form.setVerticalSpacing(10)
        display_form.addRow("Scaler", self.scaler)
        display_form.addRow("Color profile", self.color_profile)
        display_card.content.addLayout(display_form)

        audio_card = SurfaceCard()
        audio_form = QFormLayout()
        audio_form.setContentsMargins(0, 0, 0, 0)
        audio_form.setHorizontalSpacing(16)
        audio_form.setVerticalSpacing(10)
        audio_form.addRow("Output", self.audio_output)
        audio_form.addRow("Volume", self.volume)
        audio_card.content.addLayout(audio_form)

        self.save_button = AccentButton("Save settings", NINTENDO_RED)
        self.save_button.clicked.connect(self.save_settings)
        cancel = QPushButton("Close")
        cancel.clicked.connect(self.reject)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(cancel)
        actions.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(header)
        layout.addWidget(self.status)
        layout.addWidget(general_card)
        layout.addWidget(display_card)
        layout.addWidget(audio_card)
        layout.addStretch(1)
        layout.addLayout(actions)

        self._load()

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _bool_value(value: str, default: bool = False) -> bool:
        if value.strip().lower() == "true":
            return True
        if value.strip().lower() == "false":
            return False
        return default

    def _load(self) -> None:
        if not self.config_path.is_file():
            self.status.setText(
                "No config.ini was found. Launch open_agb_firm once on the 3DS so it creates a version-matched configuration file, then reopen this dialog."
            )
            self.save_button.setEnabled(False)
            return
        try:
            text = self.config_path.read_text(encoding="utf-8")
        except OSError as exc:
            self.status.setText(f"Unable to read {self.config_path}: {exc}")
            self.save_button.setEnabled(False)
            return

        format_name = detect_open_agb_config_format(text)
        if format_name != "current":
            self.status.setText(
                "This open_agb_firm configuration is legacy or unknown. RommHeld will not rewrite it. Update/open open_agb_firm and let that installed version generate a fresh config.ini first."
            )
            self.save_button.setEnabled(False)
            return

        values = parse_open_agb_values(text)
        general = values.get("general", {})
        video = values.get("video", {})
        audio = values.get("audio", {})

        self.direct_boot.setChecked(self._bool_value(general.get("directBoot", "false")))
        self.use_saves_folder.setChecked(
            self._bool_value(general.get("useSavesFolder", "true"), True)
        )
        try:
            self.backlight.setValue(int(general.get("backlight", "64")))
        except ValueError:
            self.backlight.setValue(64)
        self._set_combo_value(self.scaler, video.get("scaler", "matrix"))
        self._set_combo_value(self.color_profile, video.get("colorProfile", "none"))
        self._set_combo_value(self.audio_output, audio.get("audioOut", "auto"))
        try:
            self.volume.setValue(int(audio.get("volume", "127")))
        except ValueError:
            self.volume.setValue(127)

        self.status.setText(f"Editing {self.config_path}")
        self.save_button.setEnabled(True)

    def save_settings(self) -> None:
        updates = {
            ("general", "directBoot"): self.direct_boot.isChecked(),
            ("general", "useSavesFolder"): self.use_saves_folder.isChecked(),
            ("general", "backlight"): self.backlight.value(),
            ("video", "scaler"): str(self.scaler.currentData()),
            ("video", "colorProfile"): str(self.color_profile.currentData()),
            ("audio", "audioOut"): str(self.audio_output.currentData()),
            ("audio", "volume"): self.volume.value(),
        }
        try:
            path = write_open_agb_config(self.sd_root, updates)
        except Exception as exc:
            QMessageBox.warning(self, "Unable to save open_agb_firm settings", str(exc))
            return
        QMessageBox.information(
            self,
            "open_agb_firm settings saved",
            f"Updated {path}. The previous configuration is retained as a RommHeld backup.",
        )
        self.accept()
