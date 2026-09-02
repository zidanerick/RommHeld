from __future__ import annotations


def default_3ds_destination(game_name: str, suffix: str) -> str:
    """Return conservative destinations for formats with documented 3DS paths."""
    suffix = suffix.lower()
    if suffix == ".nds":
        return f"/roms/nds/{game_name}"
    if suffix == ".gba":
        return f"/roms/gba/{game_name}"
    return game_name
