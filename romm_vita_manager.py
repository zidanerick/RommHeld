#!/usr/bin/env python3
"""
RomM Vita Manager v0.4

A simple Linux GUI for transferring games from a local RomM library
to a USB-mounted PS Vita using RetroFlow/Adrenaline conventions.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

DEFAULT_ROMM_ROOT = Path.home() / "RomM" / "roms" / "roms"
RETROFLOW_FOLDERS = {
    "Atari - 2600": "Atari - 2600", "Atari - 5200": "Atari - 5200", "Atari - 7800": "Atari - 7800",
    "Atari - Lynx": "Atari - Lynx", "Atari - ST": "Atari - ST", "Bandai - WonderSwan": "Bandai - WonderSwan",
    "Bandai - WonderSwan Color": "Bandai - WonderSwan Color", "Coleco - ColecoVision": "Coleco - ColecoVision",
    "Commodore - 64": "Commodore - 64", "Commodore - Amiga": "Commodore - Amiga", "DOS": "DOS",
    "EasyRPG": "EasyRPG", "FBA 2012": "FBA 2012", "GCE - Vectrex": "GCE - Vectrex",
    "Lexaloffle Games - Pico-8": "Lexaloffle Games - Pico-8", "MAME 2000": "MAME 2000",
    "MAME 2003 Plus": "MAME 2003 Plus", "Microsoft - MSX": "Microsoft - MSX", "Microsoft - MSX2": "Microsoft - MSX2",
    "NEC - PC Engine": "NEC - PC Engine", "NEC - PC Engine CD": "NEC - PC Engine CD", "NEC - TurboGrafx 16": "NEC - TurboGrafx 16",
    "NEC - TurboGrafx CD": "NEC - TurboGrafx CD", "Nintendo - Game Boy": "Nintendo - Game Boy",
    "Nintendo - Game Boy Advance": "Nintendo - Game Boy Advance", "Nintendo - Game Boy Color": "Nintendo - Game Boy Color",
    "Nintendo - Nintendo 64": "Nintendo - Nintendo 64", "Nintendo - Nintendo Entertainment System": "Nintendo - Nintendo Entertainment System",
    "Nintendo - Super Nintendo Entertainment System": "Nintendo - Super Nintendo Entertainment System", "ScummVM": "ScummVM",
    "Sega - 32X": "Sega - 32X", "Sega - Dreamcast": "Sega - Dreamcast", "Sega - Game Gear": "Sega - Game Gear",
    "Sega - Master System - Mark III": "Sega - Master System - Mark III", "Sega - Mega-CD - Sega CD": "Sega - Mega-CD - Sega CD",
    "Sega - Mega Drive - Genesis": "Sega - Mega Drive - Genesis", "Sinclair - ZX Spectrum": "Sinclair - ZX Spectrum",
    "SNK - Neo Geo - FBA 2012": "SNK - Neo Geo - FBA 2012", "SNK - Neo Geo Pocket Color": "SNK - Neo Geo Pocket Color",
    "Sony - PlayStation - RetroArch": "Sony - PlayStation - RetroArch",
}
ROM_EXTENSIONS = {".vpk", ".iso", ".cso", ".pbp", ".cue", ".bin", ".chd", ".zip", ".7z", ".rar", ".nes", ".fds", ".smc", ".sfc", ".gba", ".gb", ".gbc", ".md", ".gen", ".sms", ".gg", ".32x", ".pce", ".sg", ".a26", ".a52", ".a78", ".lnx", ".nds", ".n64", ".z64", ".v64", ".wbfs", ".rvz", ".gdi", ".cdi", ".adx", ".tap", ".dsk", ".hdf", ".iso2", ".3do"}

@dataclass(frozen=True)
class Game:
    path: Path
    name: str
    source_platform: str
    size: int
    relative: Path

def human_size(value: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    n = float(value)
    for unit in units:
        if n < 1024 or unit == units[-1]: return f"{n:.1f} {unit}"
        n /= 1024
    return f"{value} B"

def sanitize_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name.rstrip(".") or "Game"

def find_vita_mounts() -> list[Path]:
    user = os.environ.get("USER", "")
    base = Path("/run/media") / user
    if not base.exists(): return []
    mounts = []
    for mount in sorted(base.iterdir()):
        if not mount.is_dir(): continue
        score = sum(int((mount / marker).exists()) for marker in ("app", "appmeta", "data", "pspemu", "tai", "VitaShell"))
        if score >= 3: mounts.append(mount)
    return mounts

def scan_games(root: Path) -> list[Game]:
    if not root.exists(): return []
    games = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in ROM_EXTENSIONS: continue
        try: size = path.stat().st_size
        except OSError: continue
        relative = path.relative_to(root)
        platform = relative.parts[0] if len(relative.parts) > 1 else "Uncategorised"
        games.append(Game(path, path.stem, platform, size, relative))
    return sorted(games, key=lambda g: (g.source_platform.lower(), g.name.lower()))

def normalise_platform(text: str) -> str:
    t = text.lower()
    replacements = {"sony - playstation portable":"psp", "playstation portable":"psp", "sony psp":"psp", "psp":"psp", "sony - playstation":"playstation", "playstation":"playstation", "ps1":"playstation", "psx":"playstation", "sony - playstation vita":"vita", "playstation vita":"vita", "ps vita":"vita", "vita":"vita"}
    return replacements.get(t, t)

def destination_for_game(vita: Path, game: Game) -> tuple[str, Path, str]:
    platform = normalise_platform(game.source_platform)
    if platform == "psp": return "PSP / Adrenaline ISO", vita / "pspemu" / "ISO", "file"
    if platform == "playstation": return "PS1 / Adrenaline GAME", vita / "pspemu" / "PSP" / "GAME", "game-folder"
    if platform == "vita": return "PS Vita VPK staging", vita / "data" / "RetroFlow" / "ROMS", "staging"
    if game.source_platform in RETROFLOW_FOLDERS:
        folder = RETROFLOW_FOLDERS[game.source_platform]
        return f"RetroFlow / {folder}", vita / "data" / "RetroFlow" / "ROMS" / folder, "file"
    aliases = {"nintendo entertainment system":"Nintendo - Nintendo Entertainment System", "nes":"Nintendo - Nintendo Entertainment System", "super nintendo":"Nintendo - Super Nintendo Entertainment System", "snes":"Nintendo - Super Nintendo Entertainment System", "game boy":"Nintendo - Game Boy", "game boy color":"Nintendo - Game Boy Color", "game boy advance":"Nintendo - Game Boy Advance", "n64":"Nintendo - Nintendo 64", "mega drive":"Sega - Mega Drive - Genesis", "genesis":"Sega - Mega Drive - Genesis", "master system":"Sega - Master System - Mark III", "game gear":"Sega - Game Gear", "dreamcast":"Sega - Dreamcast", "32x":"Sega - 32X"}
    alias = aliases.get(platform)
    if alias: return f"RetroFlow / {alias}", vita / "data" / "RetroFlow" / "ROMS" / alias, "file"
    return "Needs destination review", vita / "data" / "RetroFlow" / "ROMS", "unknown"

def game_status(vita: Path | None, game: Game) -> tuple[str, str]:
    if vita is None: return "UNKNOWN", "Vita not connected"
    _, destination, mode = destination_for_game(vita, game)
    try:
        target = destination / (sanitize_name(game.name) + "/EBOOT.PBP" if mode == "game-folder" else game.path.name)
        if not target.exists(): return "NEW", "Not on Vita"
        if target.is_file() and target.stat().st_size == game.size: return "INSTALLED", "Same-size file already present"
        return "DIFFERENT", "A file is present with a different size"
    except OSError as exc: return "UNKNOWN", str(exc)

class CopyWorker(QThread):
    progress = Signal(int, str, str); file_finished = Signal(str, str); finished_ok = Signal(int, int, int); failed = Signal(str)
    def __init__(self, jobs): super().__init__(); self.jobs = jobs; self.cancel_event = threading.Event()
    def cancel(self): self.cancel_event.set()
    def _copy_file(self, src, target, size):
        copied = 0
        with src.open("rb") as source, target.open("wb") as dest:
            while True:
                if self.cancel_event.is_set():
                    try: dest.close(); target.unlink(missing_ok=True)
                    except OSError: pass
                    return False
                chunk = source.read(8 * 1024 * 1024)
                if not chunk: break
                dest.write(chunk); copied += len(chunk); self._completed_bytes += len(chunk)
                percent = int(self._completed_bytes * 100 / self._total_bytes) if self._total_bytes else 100
                self.progress.emit(percent, src.name, f"{human_size(copied)} / {human_size(size)}")
        return True
    def run(self):
        copied = skipped = cancelled = 0
        try:
            self._total_bytes = sum(g.size for g, _, _, _ in self.jobs); self._completed_bytes = 0
            for game, destination, mode, label in self.jobs:
                if self.cancel_event.is_set(): cancelled += 1; break
                destination.mkdir(parents=True, exist_ok=True)
                if mode == "game-folder": target = destination / sanitize_name(game.name) / "EBOOT.PBP"
                else: target = destination / game.path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and target.is_file() and target.stat().st_size == game.size:
                    skipped += 1; self._completed_bytes += game.size; self.progress.emit(int(self._completed_bytes * 100 / self._total_bytes), game.name, "Already present")
                    continue
                self.progress.emit(int(self._completed_bytes * 100 / self._total_bytes) if self._total_bytes else 0, game.name, f"Copying to {label}")
                if self._copy_file(game.path, target, game.size):
                    try:
                        if target.stat().st_size != game.size: raise OSError("verification failed: destination size differs")
                    except OSError: target.unlink(missing_ok=True); raise
                    copied += 1; self.file_finished.emit(game.name, "copied")
                else: cancelled += 1; break
            self.finished_ok.emit(copied, skipped, cancelled)
        except Exception as exc: self.failed.emit(str(exc))

class SettingsDialog(QDialog):
    def __init__(self, current, parent=None):
        super().__init__(parent); self.setWindowTitle("Settings")
        self.root_edit = QLineEdit(str(current)); browse = QPushButton("Browse…"); browse.clicked.connect(self.browse)
        form = QFormLayout(); row = QHBoxLayout(); row.addWidget(self.root_edit); row.addWidget(browse); form.addRow("RomM library:", row)
        buttons = QHBoxLayout(); ok = QPushButton("OK"); cancel = QPushButton("Cancel"); ok.clicked.connect(self.accept); cancel.clicked.connect(self.reject); buttons.addStretch(); buttons.addWidget(cancel); buttons.addWidget(ok)
        layout = QVBoxLayout(self); layout.addLayout(form); layout.addLayout(buttons)
    def browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select RomM ROM directory", self.root_edit.text());
        if path: self.root_edit.setText(path)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("RomM Vita Manager v0.4"); self.resize(1250, 760); self.romm_root = DEFAULT_ROMM_ROOT; self.vita = None; self.worker = None; self.games = []; self.filtered_games = []
        top = QHBoxLayout(); self.refresh_button = QPushButton("Refresh"); self.refresh_button.clicked.connect(self.refresh_all); self.settings_button = QPushButton("Settings"); self.settings_button.clicked.connect(self.open_settings); self.search = QLineEdit(); self.search.setPlaceholderText("Search games…"); self.search.textChanged.connect(self.refresh_games); self.platforms = QComboBox(); self.platforms.currentTextChanged.connect(self.refresh_games); self.status_filter = QComboBox(); self.status_filter.addItems(["All statuses", "Not installed", "Installed", "Different", "Unknown"]); self.status_filter.currentTextChanged.connect(self.refresh_games); self.view_mode = QComboBox(); self.view_mode.addItems(["List", "Tiles"]); self.view_mode.currentTextChanged.connect(self.apply_view_mode); self.selection_label = QLabel("0 selected")
        for w in (self.refresh_button, self.settings_button, self.search, self.platforms, self.status_filter, self.view_mode, self.selection_label): top.addWidget(w)
        library_box = QGroupBox("RomM Library"); ll = QVBoxLayout(library_box); self.source_label = QLabel(); self.game_list = QListWidget(); self.game_list.setSelectionMode(QListWidget.ExtendedSelection); self.game_list.itemSelectionChanged.connect(self.update_summary); ll.addWidget(self.source_label); ll.addWidget(self.game_list)
        vita_box = QGroupBox("Vita"); vl = QVBoxLayout(vita_box); self.vita_label = QLabel(); self.destination_label = QLabel("Select a game to see its automatic destination."); self.destination_label.setWordWrap(True); self.destination_button = QPushButton("Show destination"); self.destination_button.clicked.connect(self.show_game_destination); self.copy_button = QPushButton("Copy selected"); self.copy_button.clicked.connect(self.copy_selected); self.cancel_button = QPushButton("Cancel transfer"); self.cancel_button.clicked.connect(self.cancel_copy); self.cancel_button.setEnabled(False); self.progress = QProgressBar(); self.status = QLabel("Ready")
        for w in (self.vita_label, self.destination_label, self.destination_button): vl.addWidget(w)
        vl.addStretch(); vl.addWidget(self.progress); vl.addWidget(self.status); vl.addWidget(self.copy_button); vl.addWidget(self.cancel_button)
        splitter = QSplitter(Qt.Horizontal); splitter.addWidget(library_box); splitter.addWidget(vita_box); splitter.setSizes([850, 400]); central = QWidget(); layout = QVBoxLayout(central); layout.addLayout(top); layout.addWidget(splitter, 1); self.setCentralWidget(central); self.refresh_all()
    def refresh_all(self): self.detect_vita(); self.refresh_games()
    def detect_vita(self):
        mounts = find_vita_mounts(); self.vita = mounts[0] if mounts else None
        self.vita_label.setText(f"Connected: {self.vita}" if self.vita else "No Vita detected. Connect VitaShell in USB mode, then press Refresh.")
    def refresh_games(self):
        self.games = scan_games(self.romm_root); current = self.platforms.currentText(); self.platforms.blockSignals(True); self.platforms.clear(); self.platforms.addItem("All platforms"); self.platforms.addItems(sorted({g.source_platform for g in self.games}, key=str.lower)); idx = self.platforms.findText(current); self.platforms.setCurrentIndex(idx if idx >= 0 else 0); self.platforms.blockSignals(False)
        query = self.search.text().strip().lower(); platform = self.platforms.currentText(); wanted = self.status_filter.currentText(); candidates=[]
        for game in self.games:
            if query and query not in game.name.lower(): continue
            if platform != "All platforms" and game.source_platform != platform: continue
            state, _ = game_status(self.vita, game)
            if wanted == "Not installed" and state != "NEW": continue
            if wanted == "Installed" and state != "INSTALLED": continue
            if wanted == "Different" and state != "DIFFERENT": continue
            if wanted == "Unknown" and state != "UNKNOWN": continue
            candidates.append(game)
        self.filtered_games = candidates; self.game_list.clear(); symbols={"INSTALLED":"✓", "NEW":"↓", "DIFFERENT":"↻", "UNKNOWN":"?"}
        for game in self.filtered_games:
            state, detail = game_status(self.vita, game); item=QListWidgetItem(f"{symbols.get(state,'?')} {game.name}\n{game.source_platform} • {human_size(game.size)} • {detail}"); item.setData(Qt.UserRole, game); self.game_list.addItem(item)
        self.apply_view_mode(); self.source_label.setText(f"{self.romm_root}  •  {len(self.filtered_games)} games shown"); self.update_summary()
    def apply_view_mode(self):
        if self.view_mode.currentText() == "Tiles":
            self.game_list.setViewMode(QListWidget.IconMode); self.game_list.setResizeMode(QListWidget.Adjust); self.game_list.setMovement(QListWidget.Static); self.game_list.setGridSize(__import__("PySide6.QtCore", fromlist=["QSize"]).QSize(250, 90)); self.game_list.setIconSize(__import__("PySide6.QtCore", fromlist=["QSize"]).QSize(32, 32))
        else: self.game_list.setViewMode(QListWidget.ListMode); self.game_list.setResizeMode(QListWidget.Fixed); self.game_list.setMovement(QListWidget.Static)
    def update_summary(self):
        selected=self.game_list.selectedItems(); total=sum(item.data(Qt.UserRole).size for item in selected); self.selection_label.setText(f"{len(selected)} selected • {human_size(total)}")
        if len(selected)==1: self.set_destination_for_game(selected[0].data(Qt.UserRole))
        else: self.destination_label.setText("Multiple games selected." if selected else "Select a game to see its destination.")
    def set_destination_for_game(self, game):
        if not self.vita: self.destination_label.setText("No Vita connected."); return
        label,path,mode=destination_for_game(self.vita,game); self.destination_label.setText(f"{label}\n{path}")
    def show_game_destination(self):
        selected=self.game_list.selectedItems()
        if len(selected)!=1: QMessageBox.information(self,"Select one game","Select exactly one game to see its automatic destination."); return
        self.set_destination_for_game(selected[0].data(Qt.UserRole))
    def open_settings(self):
        dialog=SettingsDialog(self.romm_root,self)
        if dialog.exec(): self.romm_root=Path(dialog.root_edit.text()).expanduser(); self.refresh_all()
    def copy_selected(self):
        if not self.vita: QMessageBox.warning(self,"Vita not connected","Connect the Vita in VitaShell USB mode first."); return
        selected=self.game_list.selectedItems()
        if not selected: QMessageBox.information(self,"Nothing selected","Select one or more games first."); return
        jobs=[]; review=[]
        for item in selected:
            game=item.data(Qt.UserRole); state,_=game_status(self.vita,game)
            if state=="INSTALLED": continue
            label,destination,mode=destination_for_game(self.vita,game)
            if mode=="unknown": review.append(f"{game.name} ({game.source_platform})"); continue
            jobs.append((game,destination,mode,label))
        if review: QMessageBox.warning(self,"Destination review required","These games could not be mapped safely and were not queued:\n\n"+"\n".join(review[:20])+("\n..." if len(review)>20 else ""))
        if not jobs: QMessageBox.information(self,"Nothing to copy","Everything selected is already present on the Vita with the expected file size."); return
        total_size=sum(game.size for game,_,_,_ in jobs)
        if QMessageBox.question(self,"Confirm copy",f"Process {len(jobs)} game(s), {human_size(total_size)}?\n\nAlready-complete files will be skipped.") != QMessageBox.StandardButton.Yes: return
        self.copy_button.setEnabled(False); self.cancel_button.setEnabled(True); self.refresh_button.setEnabled(False); self.settings_button.setEnabled(False); self.progress.setValue(0); self.status.setText("Starting transfer...")
        self.worker=CopyWorker(jobs); self.worker.progress.connect(self.on_progress); self.worker.finished_ok.connect(self.copy_finished); self.worker.failed.connect(self.copy_failed); self.worker.start()
    def cancel_copy(self):
        if not self.worker or not self.worker.isRunning(): return
        if QMessageBox.question(self,"Cancel transfer","Cancel after the current chunk finishes?\n\nThe current file will be stopped and its partial copy removed.") == QMessageBox.StandardButton.Yes: self.worker.cancel(); self.cancel_button.setEnabled(False); self.status.setText("Cancelling transfer...")
    def on_progress(self,value,message,detail): self.progress.setValue(value); self.status.setText(f"{message} • {detail}")
    def copy_finished(self,copied,skipped,cancelled):
        self.copy_button.setEnabled(True); self.cancel_button.setEnabled(False); self.refresh_button.setEnabled(True); self.settings_button.setEnabled(True); self.status.setText("Transfer cancelled." if cancelled else "Transfer complete."); self.refresh_games(); QMessageBox.information(self,"Transfer summary",f"Copied: {copied}\nSkipped (already present): {skipped}\nCancelled: {cancelled}")
    def copy_failed(self,message):
        self.copy_button.setEnabled(True); self.cancel_button.setEnabled(False); self.refresh_button.setEnabled(True); self.settings_button.setEnabled(True); self.status.setText("Transfer failed."); QMessageBox.critical(self,"Transfer failed",message)

def main():
    app=QApplication(sys.argv); app.setApplicationName("RomM Vita Manager"); app.setApplicationVersion("0.4"); window=MainWindow(); window.show(); sys.exit(app.exec())

if __name__ == "__main__": main()
