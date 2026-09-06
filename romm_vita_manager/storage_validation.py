from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StorageCheck:
    key: str
    description: str
    found: bool
    path: str


@dataclass(frozen=True)
class StorageValidation:
    kind: str
    confidence: str
    signatures: tuple[str, ...]
    checks: tuple[StorageCheck, ...] = ()

    @property
    def matched_count(self) -> int:
        return sum(check.found for check in self.checks)


def _file(root: Path, relative: str) -> bool:
    return (root / relative).is_file()


def _directory(root: Path, relative: str) -> bool:
    return (root / relative).is_dir()


def _glob_file(root: Path, relative_pattern: str) -> bool:
    return any(path.is_file() for path in root.glob(relative_pattern))


def validate_3ds_sd(root: Path) -> StorageValidation:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Storage root does not exist: {root}")

    checks = (
        StorageCheck("boot-firm", "3DS boot.firm", _file(root, "boot.firm"), "boot.firm"),
        StorageCheck("boot-3dsx", "Homebrew boot.3dsx", _file(root, "boot.3dsx"), "boot.3dsx"),
        StorageCheck("luma", "Luma3DS directory", _directory(root, "luma"), "luma/"),
        StorageCheck("godmode9", "GodMode9 directory", _directory(root, "gm9"), "gm9/"),
        StorageCheck("homebrew", "3DS homebrew directory", _directory(root, "3ds"), "3ds/"),
        StorageCheck("roms", "ROM directory", _directory(root, "roms"), "roms/"),
        StorageCheck("open-agb-firm", "open_agb_firm payload", _file(root, "luma/payloads/open_agb_firm.firm"), "luma/payloads/open_agb_firm.firm"),
        StorageCheck("nds-roms", "NDS ROM directory", _directory(root, "roms/nds"), "roms/nds/"),
    )
    signatures = tuple(check.path for check in checks if check.found)
    strong = sum(check.found for check in checks[:4])
    confidence = "high" if strong >= 3 else "medium" if strong == 2 else "low" if strong == 1 else "unknown"
    return StorageValidation("3ds-sd", confidence, signatures, checks)


def validate_ds_storage(root: Path) -> StorageValidation:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Storage root does not exist: {root}")

    bootstrap_nds = _glob_file(root, "_nds/nds-bootstrap*.nds")
    bootstrap_ver = _glob_file(root, "_nds/nds-bootstrap*.ver")
    checks = (
        StorageCheck("nds-directory", "DS support directory", _directory(root, "_nds"), "_nds/"),
        StorageCheck("twilight", "TWiLight Menu++ files", _directory(root, "_nds/TWiLightMenu"), "_nds/TWiLightMenu/"),
        StorageCheck("boot-nds", "DS root launcher", _file(root, "BOOT.NDS"), "BOOT.NDS"),
        StorageCheck("boot-alt-nds", "Alternate flashcart launcher", _file(root, "BOOT_ALT.NDS"), "BOOT_ALT.NDS"),
        StorageCheck("nds-bootstrap-nds", "nds-bootstrap runtime", bootstrap_nds, "_nds/nds-bootstrap*.nds"),
        StorageCheck("nds-bootstrap-ver", "nds-bootstrap version marker", bootstrap_ver, "_nds/nds-bootstrap*.ver"),
        StorageCheck("roms", "ROM directory", _directory(root, "roms"), "roms/"),
        StorageCheck("nds-roms", "NDS ROM directory", _directory(root, "roms/nds"), "roms/nds/"),
        StorageCheck("nds-saves", "NDS save directory", _directory(root, "roms/nds/saves"), "roms/nds/saves/"),
    )
    signatures = tuple(check.path for check in checks if check.found)
    core = sum(
        (
            _directory(root, "_nds"),
            _directory(root, "_nds/TWiLightMenu"),
            _file(root, "BOOT.NDS") or _file(root, "BOOT_ALT.NDS"),
            bootstrap_nds and bootstrap_ver,
            _directory(root, "roms"),
        )
    )
    confidence = "high" if core >= 4 else "medium" if core >= 2 else "low" if core == 1 else "unknown"
    return StorageValidation("ds-storage", confidence, signatures, checks)


def validate_ds_flashcard(root: Path) -> StorageValidation:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Storage root does not exist: {root}")

    bootstrap_nds = _glob_file(root, "_nds/nds-bootstrap*.nds")
    bootstrap_ver = _glob_file(root, "_nds/nds-bootstrap*.ver")
    checks = (
        StorageCheck("nds-bootstrap-nds", "nds-bootstrap runtime", bootstrap_nds, "_nds/nds-bootstrap*.nds"),
        StorageCheck("nds-bootstrap-ver", "nds-bootstrap version marker", bootstrap_ver, "_nds/nds-bootstrap*.ver"),
        StorageCheck("twilight", "TWiLight Menu++ files", _directory(root, "_nds/TWiLightMenu"), "_nds/TWiLightMenu/"),
        StorageCheck("boot-nds", "TWiLight root launcher", _file(root, "BOOT.NDS"), "BOOT.NDS"),
        StorageCheck("boot-alt-nds", "Alternate flashcart launcher", _file(root, "BOOT_ALT.NDS"), "BOOT_ALT.NDS"),
        StorageCheck("nds-roms", "NDS ROM directory", _directory(root, "roms/nds"), "roms/nds/"),
        StorageCheck("nds-saves", "NDS save directory", _directory(root, "roms/nds/saves"), "roms/nds/saves/"),
        StorageCheck("gba-roms", "GBA ROM directory", _directory(root, "roms/gba"), "roms/gba/"),
        StorageCheck("dsi-roms", "DSi ROM directory", _directory(root, "roms/dsi"), "roms/dsi/"),
        StorageCheck("ysmenu", "YSMenu launcher", _file(root, "YSMenu.nds"), "YSMenu.nds"),
        StorageCheck("ttmenu", "TTMenu directory", _directory(root, "TTMenu"), "TTMenu/"),
        StorageCheck("r4-data", "R4.dat", _file(root, "R4.dat"), "R4.dat"),
        StorageCheck("r4-kernel", "R4/Wood kernel directory", _directory(root, "__rpg"), "__rpg/"),
        StorageCheck("ds-menu", "Flashcart boot marker", _file(root, "_DS_MENU.DAT"), "_DS_MENU.DAT"),
        StorageCheck("dsmenu", "Flashcart boot marker", _file(root, "_DSMENU.DAT"), "_DSMENU.DAT"),
    )
    signatures = tuple(check.path for check in checks if check.found)
    twilight_capability = sum(check.found for check in checks[:7])
    explicit_marker = any(check.found for check in checks[9:])
    confidence = "high" if twilight_capability >= 5 and explicit_marker else "medium" if twilight_capability >= 2 or explicit_marker else "low" if twilight_capability == 1 else "unknown"
    return StorageValidation("ds-flashcard", confidence, signatures, checks)


def validate_storage(root: Path) -> StorageValidation:
    """Perform a read-only heuristic validation of a mounted handheld storage root."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Storage root does not exist: {root}")

    names = {entry.name.lower() for entry in root.iterdir()}
    core_3ds = {"boot.firm", "boot.3dsx", "luma", "gm9"}
    if "nintendo 3ds" in names or len(names.intersection(core_3ds)) >= 2:
        return validate_3ds_sd(root)

    flashcard_markers = {
        "r4.dat",
        "ttmenu.dat",
        "ysmenu.nds",
        "ttmenu",
        "__rpg",
        "_ds_menu.dat",
        "_dsmenu.dat",
        "boot_alt.nds",
    }
    if names.intersection(flashcard_markers):
        return validate_ds_flashcard(root)

    if "_nds" in names and ("roms" in names or "boot.nds" in names):
        return validate_ds_storage(root)

    signatures: list[str] = []
    if "roms" in names:
        signatures.append("roms/")
    if "_nds" in names:
        signatures.append("_nds/")
    return StorageValidation("unknown", "low", tuple(signatures))
