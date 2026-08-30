from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from .emulators import EMULATORS
from .vita import free_space, total_space


APP_PATTERNS = {
    "retroflow": ("retroflow",),
    "adrenaline": ("pspemucfw", "adrenaline"),
    "retroarch": ("retroarch",),
    "daedalusx64": ("daedalus", "daedalusx64"),
    "flycast": ("flycast",),
    "fake-08": ("fake-08", "fake08"),
    "scummvm": ("scummvm",),
    "dsvita": ("dsvita",),
}


def _app_dirs(vita: Path) -> list[str]:
    app = vita / "app"
    if not app.is_dir():
        return []
    try:
        return [p.name.lower() for p in app.iterdir() if p.is_dir()]
    except OSError:
        return []


def detect_installed(vita: Path) -> dict[str, bool]:
    names = _app_dirs(vita)
    result: dict[str, bool] = {}
    for emulator in EMULATORS:
        patterns = APP_PATTERNS.get(emulator.key, ())
        app_match = any(any(pattern in name for pattern in patterns) for name in names)
        data_match = any((vita / rel).exists() for rel in emulator.detection_paths)
        result[emulator.key] = app_match or data_match
    return result


class VitaSetupDialog(QDialog):
    def __init__(self, vita: Path | None, parent=None):
        super().__init__(parent)
        self.vita = vita
        self.setWindowTitle("Vita Setup")
        self.resize(760, 620)

        layout = QVBoxLayout(self)
        title = QLabel("Vita software and RetroAchievements readiness")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        if vita is None:
            message = QLabel(
                "No Vita filesystem is currently mounted. Connect VitaShell in USB mode, "
                "then reopen this screen."
            )
            message.setWordWrap(True)
            layout.addWidget(message)
            close = QPushButton("Close")
            close.clicked.connect(self.accept)
            layout.addWidget(close)
            return

        try:
            free = free_space(vita)
            total = total_space(vita)
            storage = QLabel(f"Storage: {free / 1024**3:.1f} GiB free of {total / 1024**3:.1f} GiB")
            layout.addWidget(storage)
        except OSError:
            pass

        grid_box = QGroupBox("Detected components")
        grid = QGridLayout(grid_box)
        grid.addWidget(QLabel("Component"), 0, 0)
        grid.addWidget(QLabel("Status"), 0, 1)
        grid.addWidget(QLabel("Purpose"), 0, 2)

        installed = detect_installed(vita)
        for row, emulator in enumerate(EMULATORS, 1):
            grid.addWidget(QLabel(emulator.name), row, 0)
            status = "✓ Installed" if installed.get(emulator.key) else "? Not detected"
            grid.addWidget(QLabel(status), row, 1)
            grid.addWidget(QLabel(emulator.description), row, 2)

        layout.addWidget(grid_box)

        ra = QGroupBox("RetroAchievements")
        ra_layout = QVBoxLayout(ra)
        ra_text = QLabel(
            "For systems supported by RetroAchievements, the preferred path is RetroArch "
            "with an appropriate libretro core. RetroFlow itself is a launcher and does not "
            "provide the achievement implementation. N64 is kept separate here because "
            "RetroFlow commonly uses DaedalusX64 for N64, while achievement setups may "
            "require a different RetroArch/core arrangement."
        )
        ra_text.setWordWrap(True)
        ra_layout.addWidget(ra_text)
        retroarch_state = "available" if installed.get("retroarch") else "not detected"
        ra_layout.addWidget(QLabel(f"RetroArch: {retroarch_state}"))
        n64_state = "available" if installed.get("daedalusx64") else "not detected"
        ra_layout.addWidget(QLabel(f"DaedalusX64: {n64_state}"))
        layout.addWidget(ra)

        note = QLabel(
            "This screen currently detects components only. It does not install VPKs automatically. "
            "That keeps the setup safe while we add verified download sources and version checks."
        )
        note.setWordWrap(True)
        note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(note)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
