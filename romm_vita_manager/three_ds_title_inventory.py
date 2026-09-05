from __future__ import annotations

from pathlib import Path

from .three_ds_storage import configured_3ds_storage_root


def _hex_directory(path: Path, length: int) -> bool:
    if path.is_symlink():
        return False
    try:
        if not path.is_dir():
            return False
    except OSError:
        return False
    name = path.name
    return len(name) == length and all(ch in "0123456789abcdefABCDEF" for ch in name)


def _children(path: Path) -> tuple[Path, ...]:
    try:
        return tuple(path.iterdir())
    except OSError:
        return ()


def mounted_sd_title_ids(root: str | Path) -> frozenset[bytes]:
    """Return Title IDs visible in a mounted Nintendo 3DS SD title tree.

    SD application data uses:
        Nintendo 3DS/<ID0>/<ID1>/title/<Title ID High>/<Title ID Low>/...

    This is deliberately a directory-name inventory only. RommHeld does not
    decrypt title contents or parse the console's encrypted title database.
    """

    base = Path(root).expanduser() / "Nintendo 3DS"
    try:
        if not base.is_dir():
            return frozenset()
    except OSError:
        return frozenset()

    found: set[bytes] = set()
    for id0 in _children(base):
        if not _hex_directory(id0, 32):
            continue
        for id1 in _children(id0):
            if not _hex_directory(id1, 32):
                continue
            title_root = id1 / "title"
            try:
                if not title_root.is_dir() or title_root.is_symlink():
                    continue
            except OSError:
                continue
            for high in _children(title_root):
                if not _hex_directory(high, 8):
                    continue
                for low in _children(high):
                    if not _hex_directory(low, 8):
                        continue
                    try:
                        found.add(bytes.fromhex(high.name + low.name))
                    except ValueError:
                        continue
    return frozenset(found)


def configured_mounted_sd_title_ids(config: dict) -> frozenset[bytes]:
    """Return visible installed SD Title IDs when a validated mount is configured."""

    root = configured_3ds_storage_root(config)
    if root is None:
        return frozenset()
    return mounted_sd_title_ids(root)


__all__ = ["configured_mounted_sd_title_ids", "mounted_sd_title_ids"]
