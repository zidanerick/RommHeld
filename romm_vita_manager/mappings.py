from __future__ import annotations

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


def normalize_platform_slug(platform: str) -> str:
    """Normalize a RomM slug or mapped display label to the canonical slug."""
    raw = str(platform or "").strip()
    folded = raw.casefold()
    if folded in PLATFORM_LABELS:
        return folded
    for slug, label in PLATFORM_LABELS.items():
        if label.casefold() == folded:
            return slug
    return folded


def platform_label(platform: str) -> str:
    return PLATFORM_LABELS.get(normalize_platform_slug(platform), platform)
