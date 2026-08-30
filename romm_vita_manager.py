#!/usr/bin/env python3
"""RomM Vita Manager.

Linux GUI for transferring a local RomM library to a USB-mounted modded PS Vita.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QHeaderView,
)

APP_DIR = Path.home() / ".config" / "romm-vita-manager"
CONFIG_PATH = APP_DIR / "config.json"
DEFAULT_ROMM_ROOT = Path.home() / "RomM" / "roms" / "roms"

RETROFLOW_FOLDERS = [
    "Atari - 2600", "Atari - 5200", "Atari - 7800", "Atari - Lynx", "Atari - ST",
    "Bandai - WonderSwan", "Bandai - WonderSwan Color", "Coleco - ColecoVision",
    "Commodore - 64", "Commodore - Amiga", "DOS", "EasyRPG", "FBA 2012",
    "GCE - Vectrex", "Lexaloffle Games - Pico-8", "MAME 2000", "MAME 2003 Plus",
    "Microsoft - MSX", "Microsoft - MSX2", "NEC - PC Engine", "NEC - PC Engine CD",
    "NEC - TurboGrafx 16", "NEC - TurboGrafx CD", "Nintendo - Game Boy",
    "Nintendo - Game Boy Advance", "Nintendo - Game Boy Color", "Nintendo - Nintendo 64",
    "Nintendo - Nintendo Entertainment System", "Nintendo - Super Nintendo Entertainment System",
    "ScummVM", "Sega - 32X", "Sega - Dreamcast", "Sega - Game Gear",
    "Sega - Master System - Mark III", "Sega - Mega-CD - Sega CD", "Sega - Mega Drive - Genesis",
    "Sinclair - ZX Spectrum", "SNK - Neo Geo - FBA 2012", "SNK - Neo Geo Pocket Color",
    "Sony - PlayStation - RetroArch",
]

PLATFORM_LABELS = {
    "3do": "3DO", "3ds": "Nintendo 3DS", "64dd": "Nintendo 64DD", "acpc": "Amstrad CPC",
    "amiga": "Commodore Amiga", "arcade": "Arcade", "atari2600": "Atari 2600",
    "atari5200": "Atari 5200", "atari7800": "Atari 7800", "atari-jaguar-cd": "Atari Jaguar CD",
    "atari-st": "Atari ST", "c64": "Commodore 64", "colecovision": "ColecoVision",
    "dc": "Sega Dreamcast", "dos": "DOS", "famicom": "Famicom", "fds": "Famicom Disk System",
    "gamegear": "Sega Game Gear", "gb": "Game Boy", "gba": "Game Boy Advance", "gbc": "Game Boy Color",
    "gc": "Nintendo GameCube", "genesis": "Sega Mega Drive / Genesis", "intellivision": "Intellivision",
    "jaguar": "Atari Jaguar", "lynx": "Atari Lynx", "msx": "MSX", "n64": "Nintendo 64",
    "nds": "Nintendo DS", "neogeomvs": "Neo Geo MVS", "neo-geo-pocket": "Neo Geo Pocket",
    "neo-geo-pocket-color": "Neo Geo Pocket Color", "nes": "NES", "pc-fx": "PC-FX", "ps2": "PlayStation 2",
    "psp": "PSP", "psx": "PlayStation", "saturn": "Sega Saturn", "scummvm": "ScummVM",
    "sega32": "Sega 32X", "segacd": "Sega CD", "sg1000": "SG-1000", "sms": "Master System",
    "snes": "Super Nintendo", "turbografx-cd": "TurboGrafx CD", "vectrex": "Vectrex",
    "virtualboy": "Virtual Boy", "wii": "Nintendo Wii", "wiiu": "Nintendo Wii U",
    "wonderswan": "WonderSwan", "wonderswan-color": "WonderSwan Color", "zxs": "ZX Spectrum",
}

ROMM_TO_RETROFLOW = {
    "nes": "Nintendo - Nintendo Entertainment System", "famicom": "Nintendo - Nintendo Entertainment System",
    "fds": "Nintendo - Nintendo Entertainment System", "gb": "Nintendo - Game Boy",
    "gbc": "Nintendo - Game Boy Color", "gba": "Nintendo - Game Boy Advance", "n64": "Nintendo - Nintendo 64",
    "snes": "Nintendo - Super Nintendo Entertainment System", "atari2600": "Atari - 2600",
    "atari5200": "Atari - 5200", "atari7800": "Atari - 7800", "lynx": "Atari - Lynx",
    "atari-st": "Atari - ST", "c64": "Commodore - 64", "amiga": "Commodore - Amiga", "dos": "DOS",
    "scummvm": "ScummVM", "colecovision": "Coleco - ColecoVision", "msx": "Microsoft - MSX",
    "sms": "Sega - Master System - Mark III", "gamegear": "Sega - Game Gear", "genesis": "Sega - Mega Drive - Genesis",
    "dc": "Sega - Dreamcast", "sega32": "Sega - 32X", "segacd": "Sega - Mega-CD - Sega CD",
    "turbografx-cd": "NEC - TurboGrafx CD", "vectrex": "GCE - Vectrex", "wonderswan": "Bandai - WonderSwan",
    "wonderswan-color": "Bandai - WonderSwan Color", "neo-geo-pocket-color": "SNK - Neo Geo Pocket Color",
    "neogeomvs": "SNK - Neo Geo - FBA 2012", "zxs": "Sinclair - ZX Spectrum",
}

EXTENSIONS = {
    ".vpk", ".iso", ".cso", ".pbp", ".cue", ".bin", ".chd", ".zip", ".7z", ".rar", ".nes", ".fds",
    ".smc", ".sfc", ".gba", ".gb", ".gbc", ".md", ".gen", ".sms", ".gg", ".32x", ".pce", ".sg",
    ".a26", ".a52", ".a78", ".lnx", ".nds", ".n64", ".z64", ".v64", ".wbfs", ".rvz", ".gdi",
    ".cdi", ".tap", ".dsk", ".hdf", ".3do", ".uae",
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


def platform_label(platform: str) -> str:
    return PLATFORM_LABELS.get(platform.lower(), platform)


def sanitize_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", " ", name).strip().rstrip(".")
    return name or "Game"


def load_config() -> dict:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(config: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_PATH)


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
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        relative = path.relative_to(root)
        platform = relative.parts[0] if len(relative.parts) > 1 else "Uncategorised"
        games.append(Game(path, path.stem, platform, size, relative))
    return sorted(games, key=lambda g: (platform_label(g.source_platform).lower(), g.name.lower()))


def destination_for_game(vita: Path, game: Game, mappings: dict[str, str | None]):
    key = game.source_platform.lower()
    if key == "psp":
        return "PSP / Adrenaline ISO", vita / "pspemu" / "ISO", "file"
    if key in {"psx", "ps1", "playstation"}:
        return "PS1 / Adrenaline GAME", vita / "pspemu" / "PSP" / "GAME", "game-folder"
    if key == "vita":
        return "PS Vita VPK staging", vita / "data" / "RetroFlow" / "ROMS", "staging"
    folder = mappings.get(key)
    if folder:
        return f"RetroFlow / {folder}", vita / "data" / "RetroFlow" / "ROMS" / folder, "file"
    return "Needs destination review", vita / "data" / "RetroFlow" / "ROMS", "unknown"


def destination_target(vita: Path, game: Game, mappings: dict[str, str | None]):
    label, destination, mode = destination_for_game(vita, game, mappings)
    if mode == "game-folder":
        return label, destination / sanitize_name(game.name) / "EBOOT.PBP", mode
    return label, destination / game.path.name, mode


def game_status(vita: Path | None, game: Game, mappings: dict[str, str | None]):
    if vita is None:
        return "UNKNOWN", "Vita not connected"
    label, target, mode = destination_target(vita, game, mappings)
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


class SetupWizard(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RomM Vita Manager Setup")
        self.resize(980, 650)
        self.config = dict(config)
        self.root_edit = QLineEdit(str(Path(config.get("romm_root", DEFAULT_ROMM_ROOT)).expanduser()))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.browse_root)
        row = QHBoxLayout(); row.addWidget(self.root_edit, 1); row.addWidget(browse)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["RomM platform", "Vita destination", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)

        save = QPushButton("Finish setup")
        save.clicked.connect(self.accept_setup)
        layout = QVBoxLayout(self)
        intro = QLabel("Choose the main RomM ROM directory, then review the automatic console mappings. The configuration is stored locally on this computer.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout(); form.addRow("Main RomM ROM directory:", row); layout.addLayout(form)
        layout.addWidget(self.table, 1); layout.addWidget(save)
        self.root_edit.textChanged.connect(self.scan_root)
        self.scan_root()

    def browse_root(self):
        path = QFileDialog.getExistingDirectory(self, "Select RomM ROM directory", self.root_edit.text())
        if path:
            self.root_edit.setText(path)

    def scan_root(self):
        root = Path(self.root_edit.text()).expanduser()
        dirs = sorted([p.name for p in root.iterdir() if p.is_dir()], key=str.lower) if root.is_dir() else []
        old = self.config.get("platform_mappings", {})
        self.table.setRowCount(len(dirs))
        for row, source in enumerate(dirs):
            key = source.lower()
            item = QTableWidgetItem(platform_label(source))
            item.setData(Qt.UserRole, source)
            self.table.setItem(row, 0, item)
            combo = QComboBox(); combo.addItem("Disabled", None)
            if key == "psp":
                combo.addItem("Adrenaline / PSP ISO", "__PSP__"); combo.setCurrentIndex(1)
            elif key in {"psx", "ps1", "playstation"}:
                combo.addItem("Adrenaline / PS1 GAME", "__PS1__"); combo.setCurrentIndex(1)
            for folder in RETROFLOW_FOLDERS:
                combo.addItem(f"RetroFlow / {folder}", folder)
            suggested = old.get(key)
            if suggested is None:
                suggested = ROMM_TO_RETROFLOW.get(key)
            idx = combo.findData(suggested)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            self.table.setCellWidget(row, 1, combo)
            status = "Recommended" if combo.currentData() else "Disabled"
            self.table.setItem(row, 2, QTableWidgetItem(status))

    def accept_setup(self):
        root = Path(self.root_edit.text()).expanduser()
        if not root.is_dir():
            QMessageBox.warning(self, "Library not found", "Choose an existing RomM ROM directory.")
            return
        mappings = {}
        for row in range(self.table.rowCount()):
            source = self.table.item(row, 0).data(Qt.UserRole).lower()
            mappings[source] = self.table.cellWidget(row, 1).currentData()
        self.config.update({"version": 1, "setup_complete": True, "romm_root": str(root), "platform_mappings": mappings})
        save_config(self.config)
        self.accept()


class SettingsDialog(SetupWizard):
    def __init__(self, config: dict, parent=None):
        super().__init__(config, parent)
        self.setWindowTitle("RomM Vita Manager Settings")


class CopyWorker(QThread):
    progress = Signal(int, str, str)
    finished_ok = Signal(int, int, int)
    failed = Signal(str)

    def __init__(self, jobs):
        super().__init__(); self.jobs = jobs; self.cancel_event = threading.Event()

    def cancel(self): self.cancel_event.set()

    def run(self):
        copied = skipped = cancelled = 0
        try:
            total = sum(game.size for game, *_ in self.jobs) or 1
            completed = 0
            for game, destination, mode, label in self.jobs:
                if self.cancel_event.is_set():
                    cancelled += 1; break
                destination.mkdir(parents=True, exist_ok=True)
                if mode == "game-folder":
                    target = destination / sanitize_name(game.name) / "EBOOT.PBP"
                else:
                    target = destination / game.path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and target.is_file() and target.stat().st_size == game.size:
                    skipped += 1; completed += game.size
                    self.progress.emit(int(completed * 100 / total), game.name, "Already present")
                    continue
                target.unlink(missing_ok=True)
                bytes_done = 0
                with game.path.open("rb") as source, target.open("wb") as dest:
                    while True:
                        if self.cancel_event.is_set():
                            try: dest.close(); target.unlink(missing_ok=True)
                            except OSError: pass
                            cancelled += 1; break
                        chunk = source.read(8 * 1024 * 1024)
                        if not chunk: break
                        dest.write(chunk); bytes_done += len(chunk); completed += len(chunk)
                        self.progress.emit(int(completed * 100 / total), game.name,
                                           f"{human_size(bytes_done)} / {human_size(game.size)} → {label}")
                if cancelled: break
                if target.stat().st_size != game.size:
                    raise IOError(f"Size verification failed for {game.name}")
                copied += 1
            self.finished_ok.emit(copied, skipped, cancelled)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.romm_root = Path(config.get("romm_root", DEFAULT_ROMM_ROOT)).expanduser()
        self.mappings = config.get("platform_mappings", {})
        self.vita = None
        self.games = []
        self.filtered_games = []
        self.worker = None
        self.setWindowTitle("RomM Vita Manager")
        self.resize(1250, 760)

        self.search = QLineEdit(); self.search.setPlaceholderText("Search games…")
        self.platforms = QComboBox(); self.platforms.addItem("All platforms")
        self.status_filter = QComboBox(); self.status_filter.addItems(["All games", "Not installed", "Installed", "Different", "Unknown"])
        self.view_mode = QComboBox(); self.view_mode.addItems(["List", "Tiles"])
        self.game_list = QListWidget(); self.game_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.game_list.itemSelectionChanged.connect(self.update_summary)
        self.vita_label = QLabel("Not detected")
        self.source_label = QLabel(); self.selection_label = QLabel("0 selected")
        self.destination_label = QLabel("Select a game to see its destination.")
        self.progress = QProgressBar(); self.status = QLabel("Ready.")
        self.refresh_button = QPushButton("Refresh"); self.settings_button = QPushButton("Settings")
        self.copy_button = QPushButton("Copy selected → Vita"); self.cancel_button = QPushButton("Cancel transfer")
        self.cancel_button.setEnabled(False); self.destination_button = QPushButton("Show destination")
        self.refresh_button.clicked.connect(self.refresh_all); self.settings_button.clicked.connect(self.open_settings)
        self.copy_button.clicked.connect(self.copy_selected); self.cancel_button.clicked.connect(self.cancel_copy)
        self.destination_button.clicked.connect(self.show_game_destination)
        self.search.textChanged.connect(self.refresh_games); self.platforms.currentIndexChanged.connect(self.refresh_games)
        self.status_filter.currentIndexChanged.connect(self.refresh_games); self.view_mode.currentIndexChanged.connect(self.apply_view_mode)

        top = QHBoxLayout(); top.addWidget(QLabel("Search:")); top.addWidget(self.search, 1); top.addWidget(self.refresh_button); top.addWidget(self.settings_button)
        library_box = QGroupBox("RomM Library"); library_layout = QVBoxLayout(library_box)
        filter_row = QHBoxLayout(); filter_row.addWidget(QLabel("Platform:")); filter_row.addWidget(self.platforms, 1); filter_row.addWidget(QLabel("Show:")); filter_row.addWidget(self.status_filter); filter_row.addWidget(QLabel("View:")); filter_row.addWidget(self.view_mode); library_layout.addLayout(filter_row)
        library_layout.addWidget(self.source_label); library_layout.addWidget(self.game_list, 1); library_layout.addWidget(self.selection_label); library_layout.addWidget(QLabel("✓ Installed   ↓ New   ↻ Different   ? Unknown"))
        vita_box = QGroupBox("Vita"); vita_layout = QVBoxLayout(vita_box); vita_layout.addWidget(self.vita_label); vita_layout.addWidget(QLabel("Automatic destination:")); vita_layout.addWidget(self.destination_label); vita_layout.addWidget(self.destination_button); vita_layout.addStretch(); vita_layout.addWidget(self.progress); vita_layout.addWidget(self.status); vita_layout.addWidget(self.copy_button); vita_layout.addWidget(self.cancel_button)
        splitter = QSplitter(Qt.Horizontal); splitter.addWidget(library_box); splitter.addWidget(vita_box); splitter.setSizes([850, 400])
        central = QWidget(); layout = QVBoxLayout(central); layout.addLayout(top); layout.addWidget(splitter, 1); self.setCentralWidget(central)
        self.refresh_all()

    def refresh_all(self): self.detect_vita(); self.refresh_games()

    def detect_vita(self):
        mounts = find_vita_mounts(); self.vita = mounts[0] if mounts else None
        self.vita_label.setText(f"Connected: {self.vita}" if self.vita else "No Vita detected. Connect VitaShell in USB mode, then press Refresh.")

    def refresh_games(self):
        self.games = scan_games(self.romm_root); current = self.platforms.currentText(); self.platforms.blockSignals(True); self.platforms.clear(); self.platforms.addItem("All platforms")
        self.platforms.addItems(sorted({g.source_platform for g in self.games}, key=lambda s: platform_label(s).lower()))
        idx = self.platforms.findText(current); self.platforms.setCurrentIndex(idx if idx >= 0 else 0); self.platforms.blockSignals(False)
        query = self.search.text().strip().lower(); platform = self.platforms.currentText(); wanted = self.status_filter.currentText()
        self.filtered_games = []
        for game in self.games:
            if query and query not in game.name.lower(): continue
            if platform != "All platforms" and game.source_platform != platform: continue
            state, _ = game_status(self.vita, game, self.mappings)
            if wanted == "Not installed" and state != "NEW": continue
            if wanted == "Installed" and state != "INSTALLED": continue
            if wanted == "Different" and state != "DIFFERENT": continue
            if wanted == "Unknown" and state != "UNKNOWN": continue
            self.filtered_games.append(game)
        self.game_list.clear()
        for game in self.filtered_games:
            state, detail = game_status(self.vita, game, self.mappings); symbol = STATUS_SYMBOLS[state]
            item = QListWidgetItem(f"{symbol} {game.name}\n{platform_label(game.source_platform)} • {human_size(game.size)} • {detail}"); item.setData(Qt.UserRole, game); self.game_list.addItem(item)
        self.apply_view_mode(); self.source_label.setText(f"{self.romm_root} • {len(self.filtered_games)} games shown"); self.update_summary()

    def apply_view_mode(self):
        if self.view_mode.currentText() == "Tiles":
            self.game_list.setViewMode(QListWidget.IconMode); self.game_list.setResizeMode(QListWidget.Adjust); self.game_list.setMovement(QListWidget.Static); self.game_list.setGridSize(QSize(250, 90)); self.game_list.setIconSize(QSize(32, 32))
        else:
            self.game_list.setViewMode(QListWidget.ListMode); self.game_list.setResizeMode(QListWidget.Fixed); self.game_list.setMovement(QListWidget.Static)

    def update_summary(self):
        selected = self.game_list.selectedItems(); total = sum(item.data(Qt.UserRole).size for item in selected); self.selection_label.setText(f"{len(selected)} selected • {human_size(total)}")
        if len(selected) == 1: self.set_destination_for_game(selected[0].data(Qt.UserRole))
        else: self.destination_label.setText("Multiple games selected." if selected else "Select a game to see its destination.")

    def set_destination_for_game(self, game):
        if not self.vita: self.destination_label.setText("No Vita connected."); return
        label, path, mode = destination_for_game(self.vita, game, self.mappings); self.destination_label.setText(f"{label}\n{path}")

    def show_game_destination(self):
        selected = self.game_list.selectedItems()
        if len(selected) != 1: QMessageBox.information(self, "Select one game", "Select exactly one game to see its automatic destination."); return
        self.set_destination_for_game(selected[0].data(Qt.UserRole))

    def open_settings(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec(): self.config = load_config(); self.romm_root = Path(self.config.get("romm_root", DEFAULT_ROMM_ROOT)).expanduser(); self.mappings = self.config.get("platform_mappings", {}); self.refresh_all()

    def copy_selected(self):
        if not self.vita: QMessageBox.warning(self, "Vita not connected", "Connect the Vita in VitaShell USB mode first."); return
        selected = self.game_list.selectedItems()
        if not selected: QMessageBox.information(self, "Nothing selected", "Select one or more games first."); return
        jobs = []; review = []
        for item in selected:
            game = item.data(Qt.UserRole); state, _ = game_status(self.vita, game, self.mappings)
            if state == "INSTALLED": continue
            label, destination, mode = destination_for_game(self.vita, game, self.mappings)
            if mode == "unknown": review.append(f"{game.name} ({game.source_platform})"); continue
            jobs.append((game, destination, mode, label))
        if review: QMessageBox.warning(self, "Destination review required", "These games could not be mapped safely and were not queued:\n\n" + "\n".join(review[:20]) + ("\n…" if len(review) > 20 else ""))
        if not jobs: QMessageBox.information(self, "Nothing to copy", "Everything selected is already present or unmapped."); return
        total = sum(game.size for game, *_ in jobs)
        if QMessageBox.question(self, "Confirm copy", f"Process {len(jobs)} game(s), {human_size(total)}?\n\nAlready-complete files will be skipped.") != QMessageBox.StandardButton.Yes: return
        self.copy_button.setEnabled(False); self.cancel_button.setEnabled(True); self.refresh_button.setEnabled(False); self.settings_button.setEnabled(False); self.progress.setValue(0)
        self.worker = CopyWorker(jobs); self.worker.progress.connect(self.on_progress); self.worker.finished_ok.connect(self.copy_finished); self.worker.failed.connect(self.copy_failed); self.worker.start()

    def cancel_copy(self):
        if self.worker and self.worker.isRunning(): self.worker.cancel(); self.cancel_button.setEnabled(False); self.status.setText("Cancelling transfer…")

    def on_progress(self, value, message, detail): self.progress.setValue(value); self.status.setText(f"{message} • {detail}")

    def copy_finished(self, copied, skipped, cancelled):
        self.copy_button.setEnabled(True); self.cancel_button.setEnabled(False); self.refresh_button.setEnabled(True); self.settings_button.setEnabled(True); self.status.setText("Transfer cancelled." if cancelled else "Transfer complete."); self.refresh_games(); QMessageBox.information(self, "Transfer summary", f"Copied: {copied}\nSkipped: {skipped}\nCancelled: {cancelled}")

    def copy_failed(self, message):
        self.copy_button.setEnabled(True); self.cancel_button.setEnabled(False); self.refresh_button.setEnabled(True); self.settings_button.setEnabled(True); self.status.setText("Transfer failed."); QMessageBox.critical(self, "Transfer failed", message)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RomM Vita Manager"); app.setApplicationVersion("0.5")
    config = load_config()
    if not config.get("setup_complete"):
        wizard = SetupWizard(config)
        if wizard.exec() != QDialog.DialogCode.Accepted: return
        config = load_config()
    window = MainWindow(config); window.show(); sys.exit(app.exec())


if __name__ == "__main__":
    main()
