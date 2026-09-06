from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


HEALTH_STATES = {"verified", "not_verified", "needs_attention", "missing", "not_applicable"}
PROFILE_KEYS = {"dsi-homebrew", "ds-flashcart", "3ds-hosted-twilight", "generic-removable"}


@dataclass(frozen=True)
class DsProfile:
    key: str
    name: str
    confidence: str
    evidence: tuple[str, ...] = ()
    owner: str = "ds"


@dataclass(frozen=True)
class DsHealthCheck:
    key: str
    state: str
    label: str
    summary: str
    paths: tuple[str, ...] = ()
    repair: str = "guided"
    observed_version: str = ""
    known_version: str = ""

    def __post_init__(self) -> None:
        if self.state not in HEALTH_STATES:
            raise ValueError(f"Unknown DS health state: {self.state}")


@dataclass(frozen=True)
class DsHealthReport:
    root: Path
    profile: DsProfile
    overall_state: str
    summary: str
    checks: tuple[DsHealthCheck, ...]
    notes: tuple[str, ...] = ()

    def check(self, key: str) -> DsHealthCheck:
        for item in self.checks:
            if item.key == key:
                return item
        raise KeyError(key)


@dataclass(frozen=True)
class DsKnownVersions:
    nds_bootstrap: str = "2.16.0"
    twilight_menu: str = "27.24.1"
    checked_on: str = "2026-09-06"


KNOWN_VERSIONS = DsKnownVersions()


FLASHCART_MARKERS = (
    "YSMenu.nds",
    "TTMenu",
    "TTMenu.dat",
    "R4.dat",
    "__rpg",
    "_DS_MENU.DAT",
    "_DSMENU.DAT",
)


def _exists(root: Path, relative: str) -> bool:
    return (root / relative).exists()


def _is_file(root: Path, relative: str) -> bool:
    return (root / relative).is_file()


def _is_dir(root: Path, relative: str) -> bool:
    return (root / relative).is_dir()


def _validate_root(root: Path) -> Path:
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise NotADirectoryError(f"Storage root does not exist: {resolved}")
    return resolved


def detect_ds_profile(root: Path, *, profile_hint: str | None = None) -> DsProfile:
    """Infer the DS runtime environment without claiming console-only state.

    TWiLight's root layout is intentionally not enough to distinguish a DSi SD
    card from a flashcart. Callers that know the physical environment can pass
    a profile hint; otherwise ambiguous TWiLight media remains generic.
    """
    root = _validate_root(root)

    if _is_dir(root, "Nintendo 3DS") or (
        _is_file(root, "boot.firm") and _is_dir(root, "luma")
    ):
        evidence = tuple(
            path
            for path in ("Nintendo 3DS/", "boot.firm", "luma/", "_nds/TWiLightMenu/")
            if _exists(root, path.rstrip("/"))
        )
        return DsProfile(
            "3ds-hosted-twilight",
            "3DS-hosted TWiLight Menu++",
            "high",
            evidence,
            owner="3ds",
        )

    hint = str(profile_hint or "").strip().lower()
    if hint:
        if hint not in PROFILE_KEYS - {"3ds-hosted-twilight"}:
            raise ValueError(f"Unknown DS profile hint: {profile_hint}")
        names = {
            "dsi-homebrew": "Nintendo DSi homebrew / CFW",
            "ds-flashcart": "DS / DS Lite flashcart",
            "generic-removable": "Generic removable DS storage",
        }
        return DsProfile(hint, names[hint], "explicit")

    flashcard_evidence = tuple(marker for marker in FLASHCART_MARKERS if _exists(root, marker))
    if _is_file(root, "BOOT_ALT.NDS"):
        flashcard_evidence += ("BOOT_ALT.NDS",)
    if flashcard_evidence:
        return DsProfile(
            "ds-flashcart",
            "DS / DS Lite flashcart",
            "high" if len(flashcard_evidence) >= 2 else "medium",
            flashcard_evidence,
        )

    dsi_evidence = tuple(
        path for path in ("hiya.dsi", "title/") if _exists(root, path.rstrip("/"))
    )
    if dsi_evidence:
        return DsProfile(
            "dsi-homebrew",
            "Nintendo DSi homebrew / CFW",
            "medium",
            dsi_evidence,
        )

    shared = tuple(
        path
        for path in ("_nds/", "_nds/TWiLightMenu/", "BOOT.NDS", "roms/")
        if _exists(root, path.rstrip("/"))
    )
    return DsProfile(
        "generic-removable",
        "Generic removable DS storage",
        "medium" if len(shared) >= 2 else "low",
        shared,
    )


def _version_tuple(value: str) -> tuple[int, ...]:
    match = re.search(r"(?:^|[^0-9])(\d+(?:\.\d+){1,3})(?:[^0-9]|$)", value)
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def _read_version_marker(path: Path) -> str:
    try:
        text = path.read_bytes()[:256].decode("utf-8", errors="ignore")
    except OSError:
        return ""
    match = re.search(r"\b(?:v)?(\d+(?:\.\d+){1,3})\b", text, re.IGNORECASE)
    return match.group(1) if match else ""


def _bootstrap_files(root: Path) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    nds_dir = root / "_nds"
    if not nds_dir.is_dir():
        return (), ()
    launchers = tuple(sorted(path for path in nds_dir.glob("nds-bootstrap*.nds") if path.is_file()))
    versions = tuple(sorted(path for path in nds_dir.glob("nds-bootstrap*.ver") if path.is_file()))
    return launchers, versions


def _bootstrap_health(root: Path, versions: DsKnownVersions) -> DsHealthCheck:
    launchers, markers = _bootstrap_files(root)
    paths = tuple(str(path.relative_to(root)).replace("\\", "/") for path in (*launchers, *markers))
    if not launchers and not markers:
        return DsHealthCheck(
            "nds-bootstrap",
            "missing",
            "Not detected",
            "No current-layout nds-bootstrap .nds or .ver files were found directly under /_nds/.",
            repair="guided",
            known_version=versions.nds_bootstrap,
        )
    if not launchers or not markers:
        return DsHealthCheck(
            "nds-bootstrap",
            "needs_attention",
            "Partial installation",
            "nds-bootstrap runtime/version evidence is incomplete. Replace the matched files using one complete maintained release rather than mixing versions.",
            paths,
            known_version=versions.nds_bootstrap,
        )

    observed = next((value for value in (_read_version_marker(path) for path in markers) if value), "")
    if observed and _version_tuple(observed) and _version_tuple(versions.nds_bootstrap):
        if _version_tuple(observed) < _version_tuple(versions.nds_bootstrap):
            return DsHealthCheck(
                "nds-bootstrap",
                "needs_attention",
                f"Outdated · v{observed}",
                f"The detected nds-bootstrap version predates the known upstream baseline v{versions.nds_bootstrap} checked {versions.checked_on}.",
                paths,
                repair="guided",
                observed_version=observed,
                known_version=versions.nds_bootstrap,
            )
    return DsHealthCheck(
        "nds-bootstrap",
        "not_verified",
        f"Present · v{observed}" if observed else "Present · Version not readable",
        "nds-bootstrap runtime and version-marker files are present, but filesystem evidence cannot prove a successful game launch.",
        paths,
        repair="guided",
        observed_version=observed,
        known_version=versions.nds_bootstrap,
    )


def _twilight_health(root: Path, versions: DsKnownVersions) -> DsHealthCheck:
    menu = root / "_nds" / "TWiLightMenu"
    support = root / "_nds"
    if menu.is_dir():
        return DsHealthCheck(
            "twilight-menu",
            "not_verified",
            "Present · Launch not verified",
            "TWiLight Menu++ assets are present. Keep the frontend and bundled nds-bootstrap files aligned when updating.",
            ("_nds/TWiLightMenu/",),
            repair="guided",
            known_version=versions.twilight_menu,
        )
    if support.is_dir():
        return DsHealthCheck(
            "twilight-menu",
            "needs_attention",
            "Partial DS runtime",
            "/_nds/ exists but the TWiLight Menu++ runtime directory is absent.",
            ("_nds/",),
            repair="guided",
            known_version=versions.twilight_menu,
        )
    return DsHealthCheck(
        "twilight-menu",
        "missing",
        "Not detected",
        "No TWiLight Menu++ runtime assets were found.",
        repair="guided",
        known_version=versions.twilight_menu,
    )


def _launcher_health(root: Path, profile: DsProfile) -> DsHealthCheck:
    boot = _is_file(root, "BOOT.NDS")
    alt = _is_file(root, "BOOT_ALT.NDS")
    paths = tuple(path for path, found in (("BOOT.NDS", boot), ("BOOT_ALT.NDS", alt)) if found)
    if profile.key == "dsi-homebrew" and not boot:
        return DsHealthCheck(
            "launcher",
            "needs_attention" if alt else "missing",
            "BOOT.NDS missing",
            "A DSi SD TWiLight installation expects BOOT.NDS at the storage root. BOOT_ALT.NDS is used only by specific flashcart paths.",
            paths,
            repair="guided",
        )
    if boot or alt:
        return DsHealthCheck(
            "launcher",
            "not_verified",
            "Present · Launch not verified",
            "A root launcher is present, but RommHeld cannot prove that the console or flashcart actually boots it.",
            paths,
            repair="guided",
        )
    return DsHealthCheck(
        "launcher",
        "missing",
        "No root launcher detected",
        "Neither BOOT.NDS nor BOOT_ALT.NDS was found at the storage root.",
        repair="guided",
    )


def _dsi_environment_health(root: Path, profile: DsProfile) -> DsHealthCheck:
    if profile.key != "dsi-homebrew":
        return DsHealthCheck(
            "dsi-environment",
            "not_applicable",
            "Not applicable",
            "DSi NAND/homebrew state is only evaluated for the DSi profile.",
            repair="none",
        )

    evidence = tuple(path for path in ("hiya.dsi", "title/") if _exists(root, path.rstrip("/")))
    detail = (
        "hiyaCFW-related SD evidence is present, but Unlaunch and the active boot target still require console confirmation."
        if evidence
        else "Unlaunch is installed to DSi NAND and cannot be proven absent or present from the mounted SD card. Confirm the boot environment on-console."
    )
    return DsHealthCheck(
        "dsi-environment",
        "not_verified",
        "Console confirmation required",
        detail,
        evidence,
        repair="manual",
    )


def _flashcart_kernel_health(root: Path, profile: DsProfile) -> DsHealthCheck:
    if profile.key != "ds-flashcart":
        return DsHealthCheck(
            "flashcart-kernel",
            "not_applicable",
            "Not applicable",
            "Flashcart kernel evidence is only evaluated for the flashcart profile.",
            repair="none",
        )

    paths: list[str] = []
    family = ""
    if _is_file(root, "YSMenu.nds") and _is_dir(root, "TTMenu"):
        paths.extend(("YSMenu.nds", "TTMenu/"))
        family = "YSMenu"
    if _is_dir(root, "__rpg"):
        paths.append("__rpg/")
        family = family or "Wood/RPG-family"
    for marker in ("R4.dat", "TTMenu.dat", "_DS_MENU.DAT", "_DSMENU.DAT"):
        if _is_file(root, marker):
            paths.append(marker)
    if not paths:
        return DsHealthCheck(
            "flashcart-kernel",
            "not_verified",
            "Kernel unknown · Cart confirmation required",
            "No kernel marker RommHeld can identify reliably was found. Flashcart boot files vary by exact hardware revision, so absence is not treated as proof that the cart is unusable.",
            repair="manual",
        )
    return DsHealthCheck(
        "flashcart-kernel",
        "not_verified",
        f"{family or 'Kernel'} evidence present · Launch not verified",
        "Recognised flashcart runtime/boot evidence is present, but the exact cart compatibility and successful boot require physical-device confirmation.",
        tuple(paths),
        repair="manual",
    )


def _rom_directory_health(root: Path) -> DsHealthCheck:
    if _is_dir(root, "roms/nds"):
        return DsHealthCheck(
            "rom-directories",
            "verified",
            "NDS content directory ready",
            "The canonical TWiLight NDS content directory exists.",
            ("roms/nds/",),
            repair="safe",
        )
    if _is_dir(root, "roms"):
        return DsHealthCheck(
            "rom-directories",
            "needs_attention",
            "NDS directory missing",
            "/roms/ exists but /roms/nds/ does not. RommHeld can create the NDS content directory without modifying runtime files.",
            ("roms/",),
            repair="safe",
        )
    return DsHealthCheck(
        "rom-directories",
        "missing",
        "ROM directories missing",
        "The canonical /roms/nds/ content path is absent. RommHeld can create it safely.",
        repair="safe",
    )


def _save_directory_health(root: Path) -> DsHealthCheck:
    if _is_dir(root, "roms/nds/saves"):
        return DsHealthCheck(
            "save-directories",
            "verified",
            "Save directory ready",
            "The TWiLight/nds-bootstrap sibling save directory exists.",
            ("roms/nds/saves/",),
            repair="safe",
        )
    return DsHealthCheck(
        "save-directories",
        "missing",
        "Save directory missing",
        "The recommended /roms/nds/saves/ directory is absent. RommHeld can create it safely.",
        repair="safe",
    )


def _looks_like_ini(path: Path) -> tuple[bool, str]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        return False, str(exc)
    if not text.strip():
        return False, "file is empty"
    meaningful = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith((";", "#"))
    ]
    if not any(line.startswith("[") and line.endswith("]") for line in meaningful):
        return False, "no INI section header found"
    if not any("=" in line for line in meaningful):
        return False, "no key/value settings found"
    return True, ""


def _config_health(root: Path) -> DsHealthCheck:
    settings = root / "_nds" / "TWiLightMenu" / "settings.ini"
    if not settings.exists():
        return DsHealthCheck(
            "config",
            "not_verified",
            "Settings not observed",
            "TWiLight settings.ini is not present. A fresh installation may create it on first launch, so absence alone is not treated as corruption.",
            repair="guided",
        )
    valid, reason = _looks_like_ini(settings)
    if not valid:
        return DsHealthCheck(
            "config",
            "needs_attention",
            "Settings file malformed",
            f"TWiLight settings.ini could not be treated as a healthy INI file: {reason}. Preserve a backup before allowing TWiLight Menu++ to regenerate it.",
            ("_nds/TWiLightMenu/settings.ini",),
            repair="guided",
        )
    return DsHealthCheck(
        "config",
        "verified",
        "Settings file readable",
        "TWiLight settings.ini contains a readable section and key/value data. RommHeld does not infer runtime compatibility from individual undocumented settings.",
        ("_nds/TWiLightMenu/settings.ini",),
        repair="guided",
    )


def _overall(profile: DsProfile, checks: tuple[DsHealthCheck, ...]) -> tuple[str, str]:
    by_key = {check.key: check for check in checks}
    if profile.key == "3ds-hosted-twilight":
        return (
            "not_verified",
            "This is a 3DS storage layout. TWiLight readiness and repair remain owned by the Nintendo 3DS workflow.",
        )
    if profile.key == "generic-removable":
        runtime_seen = any(
            by_key[key].state in {"not_verified", "verified", "needs_attention"}
            for key in ("twilight-menu", "nds-bootstrap", "launcher")
        )
        return (
            "not_verified" if runtime_seen else "needs_attention",
            "Storage can be inspected, but the physical DS environment is not distinguishable from shared filesystem markers alone.",
        )
    if profile.key == "dsi-homebrew":
        required = ("twilight-menu", "nds-bootstrap", "launcher", "rom-directories")
        if any(by_key[key].state in {"missing", "needs_attention"} for key in required):
            return "needs_attention", "The DSi storage layout is incomplete or has a component that needs repair."
        return (
            "not_verified",
            "Filesystem readiness is present, but DSi NAND boot state and an actual game launch still require console confirmation.",
        )

    rom_ok = by_key["rom-directories"].state == "verified"
    twilight_route = all(
        by_key[key].state == "not_verified"
        for key in ("twilight-menu", "nds-bootstrap", "launcher")
    )
    kernel_seen = bool(by_key["flashcart-kernel"].paths)
    if not rom_ok or not (twilight_route or kernel_seen):
        return "needs_attention", "The flashcart has no complete runtime route RommHeld can establish from filesystem evidence."
    return (
        "not_verified",
        "Flashcart runtime evidence is present, but exact cart compatibility and a successful game launch require physical-device confirmation.",
    )


def inspect_ds_runtime(
    root: Path,
    *,
    profile_hint: str | None = None,
    known_versions: DsKnownVersions = KNOWN_VERSIONS,
) -> DsHealthReport:
    root = _validate_root(root)
    profile = detect_ds_profile(root, profile_hint=profile_hint)

    storage = DsHealthCheck(
        "storage",
        "verified",
        "Storage readable",
        "The selected removable-storage root exists and is readable by RommHeld.",
        ("./",),
        repair="none",
    )
    checks = (
        storage,
        _twilight_health(root, known_versions),
        _bootstrap_health(root, known_versions),
        _launcher_health(root, profile),
        _dsi_environment_health(root, profile),
        _flashcart_kernel_health(root, profile),
        _rom_directory_health(root),
        _save_directory_health(root),
        _config_health(root),
    )
    state, summary = _overall(profile, checks)
    notes: list[str] = []
    if profile.key == "generic-removable" and _is_dir(root, "_nds/TWiLightMenu"):
        notes.append(
            "TWiLight's standard filesystem layout is shared by DSi SD and flashcart installations; select/confirm the physical environment before environment-specific repair."
        )
    if profile.key == "dsi-homebrew":
        notes.append(
            "Unlaunch is NAND-resident. SD-card inspection must never be reported as proof that Unlaunch is installed or correctly configured."
        )
    if profile.key == "3ds-hosted-twilight":
        notes.append("No DS repair action should write to this root; hand the target to the 3DS readiness workflow.")
    return DsHealthReport(root, profile, state, summary, checks, tuple(notes))


__all__ = [
    "DsHealthCheck",
    "DsHealthReport",
    "DsKnownVersions",
    "DsProfile",
    "KNOWN_VERSIONS",
    "detect_ds_profile",
    "inspect_ds_runtime",
]
