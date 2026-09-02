from __future__ import annotations

from pathlib import Path

from .models import Game

EXTENSIONS = {
    ".vpk", ".iso", ".cso", ".pbp", ".cue", ".bin", ".chd", ".zip", ".7z", ".rar",
    ".3ds", ".3dsx", ".cia",
    ".nes", ".fds", ".smc", ".sfc", ".gba", ".gb", ".gbc", ".md", ".gen", ".sms", ".gg",
    ".32x", ".pce", ".sg", ".a26", ".a52", ".a78", ".lnx", ".nds", ".n64", ".z64", ".v64",
    ".wbfs", ".rvz", ".gdi", ".cdi", ".tap", ".dsk", ".hdf", ".3do", ".uae",
}


def scan_games(root: Path) -> list[Game]:
    """Scan the RomM root. The first directory below root is the RomM platform ID."""
    if not root.is_dir():
        return []

    games: list[Game] = []
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

    return sorted(games, key=lambda game: (game.source_platform.lower(), game.name.lower()))
