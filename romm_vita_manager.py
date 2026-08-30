#!/usr/bin/env python3
"""RomM Vita Manager.

Linux GUI for transferring games from a local RomM library to a USB-mounted
PS Vita using the RetroFlow and Adrenaline directory conventions.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

DEFAULT_ROMM_ROOT = Path.home() / "RomM" / "roms" / "roms"

# Exact RetroFlow directory names observed on the target Vita.
RETROFLOW_FOLDERS = {
    "Atari - 2600": "Atari - 2600",
    "Atari - 5200": "Atari - 5200",
    "Atari - 7800": "Atari - 7800",
    "Atari - Lynx": "Atari - Lynx",
    "Atari - ST": "Atari - ST",
    "Bandai - WonderSwan": "Bandai - WonderSwan",
    "Bandai - WonderSwan Color": "Bandai - WonderSwan Color",
    "Coleco - ColecoVision": "Coleco - ColecoVision",
    "Commodore - 64": "Commodore - 64",
    "Commodore - Amiga": "Commodore - Amiga",
    "DOS": "DOS",
    "EasyRPG": "EasyRPG",
    "FBA 2012": "FBA 2012",
    "GCE - Vectrex": "GCE - Vectrex",
    "Lexaloffle Games - Pico-8": "Lexaloffle Games - Pico-8",
    "MAME 2000": "MAME 2000",
    "MAME 2003 Plus": "MAME 2003 Plus",
    "Microsoft - MSX": "Microsoft - MSX",
    "Microsoft - MSX2": "Microsoft - MSX2",
    "NEC - PC Engine": "NEC - PC Engine",
    "NEC - PC Engine CD": "NEC - PC Engine CD",
    "NEC - TurboGrafx 16": "NEC - TurboGrafx 16",
    "NEC - TurboGrafx CD": "NEC - TurboGrafx CD",
    "Nintendo - Game Boy": "Nintendo - Game Boy",
    "Nintendo - Game Boy Advance": "Nintendo - Game Boy Advance",
    "Nintendo - Game Boy Color": "Nintendo - Game Boy Color",
    "Nintendo - Nintendo 64": "Nintendo - Nintendo 64",
    "Nintendo - Nintendo Entertainment System": "Nintendo - Nintendo Entertainment System",
    "Nintendo - Super Nintendo Entertainment System": "Nintendo - Super Nintendo Entertainment System",
    "ScummVM": "ScummVM",
    "Sega - 32X": "Sega - 32X",
    "Sega - Dreamcast": "Sega - Dreamcast",
    "Sega - Game Gear": "Sega - Game Gear",
    "Sega - Master System - Mark III": "Sega - Master System - Mark III",
    "Sega - Mega-CD - Sega CD": "Sega - Mega-CD - Sega CD",
    "Sega - Mega Drive - Genesis": "Sega - Mega Drive - Genesis",
    "Sinclair - ZX Spectrum": "Sinclair - ZX Spectrum",
    "SNK - Neo Geo - FBA 2012": "SNK - Neo Geo - FBA 2012",
    "SNK - Neo Geo Pocket Color": "SNK - Neo Geo Pocket Color",
    "Sony - PlayStation - RetroArch": "Sony - PlayStation - RetroArch",
}

# RomM uses short platform IDs. Map those IDs to the descriptive RetroFlow
# directory names. Entries set to None are intentionally unsupported with the
# current RetroFlow layout discovered on the target Vita.
ROMM_TO_RETROFLOW = {
    "nes": "Nintendo - Nintendo Entertainment System",
    "famicom": "Nintendo - Nintendo Entertainment System",
    "gb": "Nintendo - Game Boy",
    "gbc": "Nintendo - Game Boy Color",
    "gba": "Nintendo - Game Boy Advance",
    "n64": "Nintendo - Nintendo 64",
    "snes": "Nintendo - Super Nintendo Entertainment System",
    "super-famicom": "Nintendo - Super Nintendo Entertainment System",
    "atari2600": "Atari - 2600",
    "atari5200": "Atari - 5200",
    "atari7800": "Atari - 7800",
    "lynx": "Atari - Lynx",
    "atari-st": "Atari - ST",
    "c64": "Commodore - 64",
    "amiga": "Commodore - Amiga",
    "dos": "DOS",
    "scummvm": "ScummVM",
    "colecovision": "Coleco - ColecoVision",
    "msx": "Microsoft - MSX",
    "sms": "Sega - Master System - Mark III",
    "gg": "Sega - Game Gear",
    "md": "Sega - Mega Drive - Genesis",
    "genesis": "Sega - Mega Drive - Genesis",
    "dc": "Sega - Dreamcast",
    "32x": "Sega - 32X",
    "pcengine": "NEC - PC Engine",
    "pce": "NEC - PC Engine",
    "pcengine-cd": "NEC - PC Engine CD",
    "mame2000": "MAME 2000",
    "mame2003-plus": "MAME 2003 Plus",
    "fba2012": "FBA 2012",
    "atari-jaguar-cd": None,
    "jaguar": None,
    "arcade": None,
    "acpc": None,
    "gc": None,
    "wii": None,
    "nds": None,
    "3ds": None,
    "3do": None,
    "ps2": None,
}

PLATFORM_LABELS = {
    "gb": "Nintendo Game Boy",
    "gbc": "Nintendo Game Boy Color",
    "gba": "Nintendo Game Boy Advance",
    "n64": "Nintendo 64",
    "nes": "Nintendo Entertainment System",
    "famicom": "Nintendo / Famicom",
    "snes": "Super Nintendo Entertainment System",
    "amiga": "Commodore Amiga",
    "c64": "Commodore 64",
    "msx": "Microsoft MSX",
    "dos": "DOS",
    "scummvm": "ScummVM",
    "atari2600": "Atari 2600",
    "atari5200": "Atari 5200",
    "atari7800": "Atari 7800",
    "lynx": "Atari Lynx",
    "atari-st": "Atari ST",
    "sms": "Sega Master System",
    "gg": "Sega Game Gear",
    "md": "Sega Mega Drive / Genesis",
    "dc": "Sega Dreamcast",
    "32x": "Sega 32X",
    "mame2000": "MAME 2000",
    "mame2003-plus": "MAME 2003 Plus",
    "fba2012": "FinalBurn Alpha 2012",
    "pcengine": "PC Engine",
    "pce": "PC Engine",
    "pcengine-cd": "PC Engine CD",
    "arcade": "Arcade",
    "gc": "Nintendo GameCube",
    "wii": "Nintendo Wii",
    "nds": "Nintendo DS",
    "3ds": "Nintendo 3DS",
    "3do": "3DO",
    "ps2": "PlayStation 2",
    "jaguar": "Atari Jaguar",
    "atari-jaguar-cd": "Atari Jaguar CD",
    "acpc": "Amstrad CPC",
}

ROM_EXTENSIONS = {
    ".vpk", ".iso", ".cso", ".pbp", ".cue", ".bin", ".chd", ".zip", ".7z", ".rar",
    ".nes", ".fds", ".smc", ".sfc", ".gba", ".gb", ".gbc", ".md", ".gen", ".sms",
    ".gg", ".32x", ".pce", ".sg", ".a26", ".a52", ".a78", ".lnx", ".nds", ".n64",
    ".z64", ".v64", ".wbfs", ".rvz", ".gdi", ".cdi", ".tap", ".dsk", ".hdf", ".3do",
}

STATUS_SYMBOLS = {"INSTALLED": "✓", "NEW": "↓", "DIFFERENT": "↻", "UNKNOWN": "?"}


@dataclass(frozen=True)
class Game:
    path: Path
    name: str
    source_platform: str
    size: int
    relative: Path


def human_size(value: int) -> str:
    n = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{value} B"


def sanitize_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", " ", name).strip().rstrip(".")
    return name or "Game"


def platform_label(platform: str) -> str:
    return PLATFORM_LABELS.get(platform.lower(), platform)


def find_vita_mounts() -> list[Path]:
    base = Path("/run/media") / os.environ.get("USER", "")
    if not base.exists():
        return []
    found = []
    for mount in sorted(base.iterdir()):
        if not mount.is_dir():
            continue
        markers = ("app", "appmeta", "data", "pspemu", "tai", "VitaShell")
        if sum((mount / marker).exists() for marker in markers) >= 3:
            found.append(mount)
    return found


def scan_games(root: Path) -> list[Game]:
    if not root.is_dir():
        return []
    games = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in ROM_EXTENSIONS:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        relative = path.relative_to(root)
        platform = relative.parts[0] if len(relative.parts) > 1 else "Uncategorised"
        games.append(Game(path, path.stem, platform, size, relative))
    return sorted(games, key=lambda g: (platform_label(g.source_platform).lower(), g.name.lower()))


def normalise_platform(text: str) -> str:
    t = text.strip().lower()
    if t in {"psp", "playstation portable", "sony - playstation portable", "sony psp"}:
        return "psp"
    if t in {"ps1", "psx", "playstation", "sony - playstation"}:
        return "playstation"
    if t in {"vita", "ps vita", "playstation vita", "sony - playstation vita"}:
        return "vita"
    return t


def destination_for_game(vita: Path, game: Game) -> tuple[str, Path, str]:
    platform = normalise_platform(game.source_platform)
    retro_root = vita / "data" / "RetroFlow" / "ROMS"

    if platform == "psp":
        return "PSP / Adrenaline ISO", vita / "pspemu" / "ISO", "file"
    if platform == "playstation":
        return "PS1 / Adrenaline GAME", vita / "pspemu" / "PSP" / "GAME", "game-folder"
    if platform == "vita":
        return "PS Vita VPK staging", retro_root, "staging"

    source_key = game.source_platform.lower()
    mapped = ROMM_TO_RETROFLOW.get(source_key)
    if mapped and mapped in RETROFLOW_FOLDERS:
        return f"RetroFlow / {mapped}", retro_root / mapped, "file"

    direct = next((name for name in RETROFLOW_FOLDERS if name.lower() == source_key), None)
    if direct:
        return f"RetroFlow / {direct}", retro_root / direct, "file"

    return "Needs destination review", retro_root, "unknown"


def destination_target(vita: Path, game: Game) -> tuple[str, Path, str]:
    label, destination, mode = destination_for_game(vita, game)
    if mode == "game-folder":
        return label, destination / sanitize_name(game.name) / "EBOOT.PBP", mode
    return label, destination / game.path.name, mode


def game_status(vita: Path | None, game: Game) -> tuple[str, str]:
    if vita is None:
        return "UNKNOWN", "Vita not connected"
    label, target, mode = destination_target(vita, game)
    if mode == "unknown":
        return "UNKNOWN", "No safe destination mapping"
    try:
        if not target.exists():
            return "NEW", f"→ {label}"
        if target.is_file() and target.stat().st_size == game.size:
            return "INSTALLED", "Same-size file already present"
        return "DIFFERENT", "Destination exists with different size"
    except OSError as exc:
        return "UNKNOWN", str(exc)


class CopyWorker(QThread):
    progress = Signal(int, str, str)
    finished_ok = Signal(int, int, int)
    failed = Signal(str)

    def __init__(self, jobs):
        super().__init__()
        self.jobs = jobs
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        copied = skipped = cancelled = 0
        try:
            total = sum(game.size for game, *_ in self.jobs) or 1
            completed = 0

            for game, destination, mode, label in self.jobs:
                if self.cancel_event.is_set():
                    cancelled += 1
                    break

                destination.mkdir(parents=True, exist_ok=True)
                if mode == "game-folder":
                    target = destination / sanitize_name(game.name) / "EBOOT.PBP"
                else:
                    target = destination / game.path.name
                target.parent.mkdir(parents=True, exist_ok=True)

                if target.exists() and target.is_file() and target.stat().st_size == game.size:
                    skipped += 1
                    completed += game.size
                    self.progress.emit(int(completed * 100 / total), game.name, "Already present")
                    continue

                bytes_done = 0
                with game.path.open("rb") as source, target.open("wb") as dest:
                    while True:
                        if self.cancel_event.is_set():
                            try:
                                dest.close()
                                target.unlink(missing_ok=True)
                            except OSError:
                                pass
                            cancelled += 1
                            break
                        chunk = source.read(8 * 1024 * 1024)
                        if not chunk:
                            break
                        dest.write(chunk)
                        bytes_done += len(chunk)
                        completed += len(chunk)
                        self.progress.emit(
                            int(completed * 100 / total),
                            game.name,
                            f"{human_size(bytes_done)} / {human_size(game.size)} → {label}",
                        )

                if cancelled:
                    break
                if target.stat().st_size != game.size:
                    raise IOError(f"Size verification failed for {game.name}")
                copied += 1

            self.finished_ok.emit(copied, skipped, cancelled)
        except Exception as exc:
            self.failed.emit(str(exc))


class SettingsDialog(QDialog):
    def __init__(self, current: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(720, 120)
        self.root_edit = QLineEdit(str(current))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.browse)
        row = QHBoxLayout()
        row.addWidget(self.root_edit, 1)
        row.addWidget(browse)
        form = QFormLayout()
        form.addRow("RomM library:", row)
        buttons = QHBoxLayout()
        ok = QPushButton("Save")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)

    def browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select RomM ROM directory", self.root_edit.text())
        if path:
            self.root_edit.setText(path)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RomM Vita Manager")
        self.resize(1320, 800)
        self.romm_root = DEFAULT_ROMM_ROOT
        self.vita: Path | None = None
        self.games: list[Game] = []
        self.worker: CopyWorker | None = None

        self.refresh_button = QPushButton("Refresh")
        self.settings_button = QPushButton("Settings")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search games…")
        self.platforms = QComboBox()
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All statuses", "Not installed", "Installed", "Different", "Unknown"])
        self.view_mode = QComboBox()
        self.view_mode.addItems(["List", "Tiles"])

        top = QHBoxLayout()
        top.addWidget(QLabel("Search:"))
        top.addWidget(self.search, 1)
        top.addWidget(QLabel("Platform:"))
        top.addWidget(self.platforms)
        top.addWidget(QLabel("Show:"))
        top.addWidget(self.status_filter)
        top.addWidget(QLabel("View:"))
        top.addWidget(self.view_mode)
        top.addWidget(self.refresh_button)
        top.addWidget(self.settings_button)

        library_box = QGroupBox("RomM Library")
        ll = QVBoxLayout(library_box)
        self.source_label = QLabel()
        self.game_list = QListWidget()
        self.game_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.selection_label = QLabel("0 selected")
        ll.addWidget(self.source_label)
        ll.addWidget(self.game_list, 1)
        ll.addWidget(self.selection_label)
        ll.addWidget(QLabel("✓ Installed   ↓ New   ↻ Different   ? Unknown"))

        vita_box = QGroupBox("Vita")
        vl = QVBoxLayout(vita_box)
        self.vita_label = QLabel()
        self.storage_label = QLabel()
        self.destination_label = QLabel("Select a game to see its automatic destination.")
        self.destination_label.setWordWrap(True)
        self.destination_button = QPushButton("Show destination")
        self.copy_button = QPushButton("Copy selected → Vita")
        self.cancel_button = QPushButton("Cancel transfer")
        self.cancel_button.setEnabled(False)
        self.progress = QProgressBar()
        self.status = QLabel("Ready")
        vl.addWidget(self.vita_label)
        vl.addWidget(self.storage_label)
        vl.addWidget(QLabel("Automatic destination:"))
        vl.addWidget(self.destination_label)
        vl.addWidget(self.destination_button)
        vl.addStretch()
        vl.addWidget(self.progress)
        vl.addWidget(self.status)
        vl.addWidget(self.copy_button)
        vl.addWidget(self.cancel_button)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(library_box)
        splitter.addWidget(vita_box)
        splitter.setSizes([900, 420])

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(top)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self.refresh_button.clicked.connect(self.refresh_all)
        self.settings_button.clicked.connect(self.open_settings)
        self.search.textChanged.connect(self.refresh_games)
        self.platforms.currentTextChanged.connect(self.refresh_games)
        self.status_filter.currentTextChanged.connect(self.refresh_games)
        self.view_mode.currentTextChanged.connect(self.apply_view_mode)
        self.game_list.itemSelectionChanged.connect(self.update_summary)
        self.destination_button.clicked.connect(self.show_game_destination)
        self.copy_button.clicked.connect(self.copy_selected)
        self.cancel_button.clicked.connect(self.cancel_copy)

        self.refresh_all()

    def refresh_all(self):
        self.detect_vita()
        self.refresh_games()

    def detect_vita(self):
        mounts = find_vita_mounts()
        self.vita = mounts[0] if mounts else None
        if self.vita:
            self.vita_label.setText(f"Connected: {self.vita}")
            try:
                usage = shutil.disk_usage(self.vita)
                self.storage_label.setText(
                    f"Storage: {human_size(usage.free)} free of {human_size(usage.total)}"
                )
            except OSError as exc:
                self.storage_label.setText(f"Storage unavailable: {exc}")
        else:
            self.vita_label.setText(
                "No Vita detected. Connect VitaShell in USB mode, then press Refresh."
            )
            self.storage_label.setText("")

    def refresh_games(self):
        self.games = scan_games(self.romm_root)
        current = self.platforms.currentText()

        self.platforms.blockSignals(True)
        self.platforms.clear()
        self.platforms.addItem("All platforms")
        for platform in sorted(
            {g.source_platform for g in self.games},
            key=lambda x: platform_label(x).lower(),
        ):
            self.platforms.addItem(platform_label(platform), platform)
        if current:
            idx = self.platforms.findText(current)
            if idx >= 0:
                self.platforms.setCurrentIndex(idx)
        self.platforms.blockSignals(False)

        query = self.search.text().strip().lower()
        platform_data = self.platforms.currentData()
        wanted = self.status_filter.currentText()
        filtered = []

        for game in self.games:
            if query and query not in game.name.lower():
                continue
            if platform_data and game.source_platform != platform_data:
                continue
            state, _ = game_status(self.vita, game)
            if wanted == "Not installed" and state != "NEW":
                continue
            if wanted == "Installed" and state != "INSTALLED":
                continue
            if wanted == "Different" and state != "DIFFERENT":
                continue
            if wanted == "Unknown" and state != "UNKNOWN":
                continue
            filtered.append(game)

        self.game_list.clear()
        for game in filtered:
            state, detail = game_status(self.vita, game)
            item = QListWidgetItem(
                f"{STATUS_SYMBOLS.get(state, '?')} {game.name}\n"
                f"{platform_label(game.source_platform)} • {human_size(game.size)} • {detail}"
            )
            item.setData(Qt.UserRole, game)
            self.game_list.addItem(item)

        self.source_label.setText(f"{self.romm_root}  •  {len(filtered)} games shown")
        self.apply_view_mode()
        self.update_summary()

    def apply_view_mode(self):
        if self.view_mode.currentText() == "Tiles":
            self.game_list.setViewMode(QListWidget.IconMode)
            self.game_list.setResizeMode(QListWidget.Adjust)
            self.game_list.setMovement(QListWidget.Static)
            self.game_list.setGridSize(QSize(280, 80))
        else:
            self.game_list.setViewMode(QListWidget.ListMode)
            self.game_list.setResizeMode(QListWidget.Fixed)
            self.game_list.setMovement(QListWidget.Static)

    def update_summary(self):
        selected = self.game_list.selectedItems()
        total = sum(item.data(Qt.UserRole).size for item in selected)
        self.selection_label.setText(f"{len(selected)} selected • {human_size(total)}")
        if len(selected) == 1:
            self.set_destination_for_game(selected[0].data(Qt.UserRole))
        elif selected:
            self.destination_label.setText("Multiple games selected.")
        else:
            self.destination_label.setText("Select a game to see its automatic destination.")

    def set_destination_for_game(self, game: Game):
        if not self.vita:
            self.destination_label.setText("No Vita connected.")
            return
        label, target, mode = destination_target(self.vita, game)
        if mode == "unknown":
            self.destination_label.setText(f"⚠ {label}\n{target}")
        else:
            self.destination_label.setText(f"{label}\n{target}")

    def show_game_destination(self):
        selected = self.game_list.selectedItems()
        if len(selected) != 1:
            QMessageBox.information(
                self,
                "Select one game",
                "Select exactly one game to see its destination.",
            )
            return
        self.set_destination_for_game(selected[0].data(Qt.UserRole))

    def open_settings(self):
        dialog = SettingsDialog(self.romm_root, self)
        if dialog.exec():
            self.romm_root = Path(dialog.root_edit.text()).expanduser()
            self.refresh_all()

    def copy_selected(self):
        if not self.vita:
            QMessageBox.warning(
                self,
                "Vita not connected",
                "Connect the Vita in VitaShell USB mode first.",
            )
            return

        selected = self.game_list.selectedItems()
        if not selected:
            QMessageBox.information(
                self,
                "Nothing selected",
                "Select one or more games first.",
            )
            return

        games = [item.data(Qt.UserRole) for item in selected]
        jobs = []
        review = []
        skipped_existing = 0

        for game in games:
            state, _ = game_status(self.vita, game)
            if state == "INSTALLED":
                skipped_existing += 1
                continue

            label, destination, mode = destination_for_game(self.vita, game)
            if mode == "unknown":
                review.append(f"{game.name} ({platform_label(game.source_platform)})")
                continue

            jobs.append((game, destination, mode, label))

        if review:
            QMessageBox.warning(
                self,
                "Destination review required",
                "These games were not queued because their platform is not mapped "
                "to a known Vita destination:\n\n"
                + "\n".join(review[:25])
                + ("\n..." if len(review) > 25 else ""),
            )

        if not jobs:
            if skipped_existing:
                QMessageBox.information(
                    self,
                    "Nothing to copy",
                    f"{skipped_existing} selected game(s) are already installed.",
                )
            return

        total_size = sum(game.size for game, *_ in jobs)
        try:
            free = shutil.disk_usage(self.vita).free
        except OSError as exc:
            QMessageBox.critical(self, "Storage check failed", str(exc))
            return

        if total_size > free:
            QMessageBox.critical(
                self,
                "Not enough Vita space",
                f"Selected transfer: {human_size(total_size)}\n"
                f"Vita free space: {human_size(free)}\n\n"
                "Remove some files or reduce the selection before copying.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Confirm transfer",
            f"Copy {len(jobs)} game(s), {human_size(total_size)}, to the Vita?\n\n"
            f"Already-installed files skipped: {skipped_existing}\n"
            f"Vita space after transfer: approximately {human_size(free - total_size)}",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.copy_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.refresh_button.setEnabled(False)
        self.settings_button.setEnabled(False)
        self.progress.setValue(0)
        self.status.setText("Starting transfer…")

        self.worker = CopyWorker(jobs)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.copy_finished)
        self.worker.failed.connect(self.copy_failed)
        self.worker.start()

    def cancel_copy(self):
        if not self.worker or not self.worker.isRunning():
            return
        if QMessageBox.question(
            self,
            "Cancel transfer",
            "Stop the transfer? The current file will be interrupted at the next "
            "chunk and its partial copy removed.",
        ) == QMessageBox.StandardButton.Yes:
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self.status.setText("Cancelling…")

    def on_progress(self, value: int, message: str, detail: str):
        self.progress.setValue(value)
        self.status.setText(f"{message} • {detail}")

    def copy_finished(self, copied: int, skipped: int, cancelled: int):
        self.copy_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.refresh_button.setEnabled(True)
        self.settings_button.setEnabled(True)
        self.status.setText("Transfer cancelled." if cancelled else "Transfer complete.")
        self.detect_vita()
        self.refresh_games()
        QMessageBox.information(
            self,
            "Transfer summary",
            f"Copied: {copied}\nSkipped (already present): {skipped}\nCancelled: {cancelled}",
        )

    def copy_failed(self, message: str):
        self.copy_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.refresh_button.setEnabled(True)
        self.settings_button.setEnabled(True)
        self.status.setText("Transfer failed.")
        QMessageBox.critical(self, "Transfer failed", message)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RomM Vita Manager")
    app.setApplicationVersion("0.5")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
