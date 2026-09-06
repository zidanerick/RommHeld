from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping


HEALTHY = "healthy"
PRESENT_UNVERIFIED = "present_unverified"
PARTIAL = "partial"
DATA_ONLY = "data_only"
MISSING = "missing"
MISCONFIGURED = "misconfigured"
OUTDATED = "outdated"
UNKNOWN = "unknown"
MANUAL_ONLY = "manual_only"

VALID_HEALTH_STATES = {
    HEALTHY,
    PRESENT_UNVERIFIED,
    PARTIAL,
    DATA_ONLY,
    MISSING,
    MISCONFIGURED,
    OUTDATED,
    UNKNOWN,
    MANUAL_ONLY,
}

STATE_LABELS = {
    HEALTHY: "Healthy",
    PRESENT_UNVERIFIED: "Present · launch not verified",
    PARTIAL: "Partial",
    DATA_ONLY: "Data/assets only",
    MISSING: "Missing",
    MISCONFIGURED: "Misconfigured",
    OUTDATED: "Outdated",
    UNKNOWN: "Not checked",
    MANUAL_ONLY: "Manual-only",
}

REPAIR_NONE = "none"
REPAIR_STAGE_VPK = "stage_vpk"
REPAIR_MANUAL = "manual_only"


@dataclass(frozen=True)
class VitaComponentHealth:
    key: str
    name: str
    state: str
    summary: str
    evidence: tuple[str, ...] = ()
    repair_mode: str = REPAIR_NONE

    def __post_init__(self) -> None:
        if self.state not in VALID_HEALTH_STATES:
            raise ValueError(f"Unknown Vita health state: {self.state}")
        if self.repair_mode not in {REPAIR_NONE, REPAIR_STAGE_VPK, REPAIR_MANUAL}:
            raise ValueError(f"Unknown Vita repair mode: {self.repair_mode}")

    @property
    def label(self) -> str:
        base = STATE_LABELS[self.state]
        if self.repair_mode == REPAIR_MANUAL and self.state in {MISSING, PARTIAL, MISCONFIGURED}:
            return f"{base} · manual setup"
        return base


@dataclass(frozen=True)
class VitaFilesystemEvidence:
    """Sanitized filesystem evidence used by Vita runtime health checks.

    Paths are Vita-style paths such as ``ux0:app/VITASHELL``. The model records
    which volumes were actually inspected, so absence on an uninspected volume is
    never treated as proof that a file is missing. ``text_files`` is intentionally
    limited to small, explicitly supplied configuration files such as taiHEN's
    config.txt. A real device dump is neither required nor persisted.
    """

    checked_volumes: frozenset[str]
    paths: frozenset[str]
    text_files: Mapping[str, str] = field(default_factory=dict, compare=False)

    @classmethod
    def from_paths(
        cls,
        paths: Iterable[str],
        *,
        checked_volumes: Iterable[str],
        text_files: Mapping[str, str] | None = None,
    ) -> "VitaFilesystemEvidence":
        checked = frozenset(_normalize_volume(value) for value in checked_volumes)
        normalized_paths = frozenset(_normalize_vita_path(value) for value in paths)
        normalized_text = {
            _normalize_vita_path(path): content
            for path, content in (text_files or {}).items()
        }
        return cls(checked, normalized_paths, normalized_text)

    @classmethod
    def from_roots(
        cls,
        *,
        ux0: Path | None = None,
        ur0: Path | None = None,
    ) -> "VitaFilesystemEvidence":
        roots = {"ux0": ux0, "ur0": ur0}
        checked: set[str] = set()
        paths: set[str] = set()
        text_files: dict[str, str] = {}

        for volume, root in roots.items():
            if root is None:
                continue
            root = root.expanduser()
            checked.add(volume)
            for relative in _PROBE_PATHS.get(volume, ()):
                candidate = root / relative
                try:
                    if candidate.exists():
                        paths.add(_normalize_vita_path(f"{volume}:{relative}"))
                except OSError:
                    continue

            config_path = root / "tai" / "config.txt"
            try:
                if config_path.is_file():
                    key = _normalize_vita_path(f"{volume}:tai/config.txt")
                    paths.add(key)
                    text_files[key] = config_path.read_text(
                        encoding="utf-8", errors="replace"
                    )
            except OSError:
                pass

            if volume == "ux0":
                for app_id in ("RETROARCH", "RETROVITA"):
                    app_root = root / "app" / app_id
                    try:
                        if app_root.is_dir():
                            for core in app_root.glob("*_libretro.self"):
                                if core.is_file():
                                    paths.add(
                                        _normalize_vita_path(
                                            f"ux0:app/{app_id}/{core.name}"
                                        )
                                    )
                    except OSError:
                        continue

        return cls(frozenset(checked), frozenset(paths), text_files)

    def volume_checked(self, volume: str) -> bool:
        return _normalize_volume(volume) in self.checked_volumes

    def exists(self, path: str) -> bool:
        return _normalize_vita_path(path) in self.paths

    def text(self, path: str) -> str | None:
        return self.text_files.get(_normalize_vita_path(path))

    def matching(self, prefix: str, suffix: str = "") -> tuple[str, ...]:
        normalized_prefix = _normalize_vita_path(prefix).rstrip("/") + "/"
        suffix = suffix.casefold()
        return tuple(
            sorted(
                path
                for path in self.paths
                if path.startswith(normalized_prefix)
                and (not suffix or path.endswith(suffix))
            )
        )


# These are deliberately narrow probes. They cover runtime/readiness evidence only
# and avoid traversing user ROM, save or application-data trees.
_PROBE_PATHS = {
    "ux0": (
        "app/VITASHELL",
        "app/VITASHELL/eboot.bin",
        "VitaShell",
        "app/RETROFLOW",
        "app/RETROFLOW/eboot.bin",
        "data/RetroFlow",
        "app/PSPEMUCFW",
        "app/PSPEMUCFW/eboot.bin",
        "app/PSPEMUCFW/sce_module/adrenaline_kernel.skprx",
        "pspemu",
        "app/RETROARCH",
        "app/RETROARCH/eboot.bin",
        "app/RETROVITA",
        "app/RETROVITA/eboot.bin",
        "data/retroarch",
        "data/retroarch/assets",
        "data/retroarch/autoconfig",
        "data/retroarch/database",
        "data/retroarch/info",
        "app/DEDALOX64",
        "app/DEDALOX64/eboot.bin",
        "data/DaedalusX64",
        "app/FLYCASTDC",
        "app/FLYCASTDC/eboot.bin",
        "app/VSCU00001",
        "app/VSCU00001/eboot.bin",
        "data/scummvm",
        "app/DSVITA000",
        "app/DSVITA000/eboot.bin",
        "data/dsvita",
        "app/FAKE00008",
        "app/FAKE00008/eboot.bin",
        "p8carts",
        "tai/config.txt",
        "tai/kubridge.skprx",
        "RetroFlow_emu4vita.vpk",
        "Adrenaline.vpk",
        "RetroArch.vpk",
        "DaedalusX64.vpk",
        "dsvita.vpk",
    ),
    "ur0": (
        "data/libshacccg.suprx",
        "data/external/libshacccg.suprx",
        "tai/config.txt",
        "tai/kubridge.skprx",
    ),
}


_APP_RULES = {
    "vitashell": {
        "name": "VitaShell",
        "app_dirs": ("ux0:app/VITASHELL",),
        "eboots": ("ux0:app/VITASHELL/eboot.bin",),
        "data": ("ux0:VitaShell",),
        "staged": (),
        "repair": REPAIR_MANUAL,
    },
    "retroflow": {
        "name": "RetroFlow Launcher",
        "app_dirs": ("ux0:app/RETROFLOW",),
        "eboots": ("ux0:app/RETROFLOW/eboot.bin",),
        "data": ("ux0:data/RetroFlow",),
        "staged": ("ux0:RetroFlow_emu4vita.vpk",),
        "repair": REPAIR_STAGE_VPK,
    },
    "adrenaline": {
        "name": "Adrenaline",
        "app_dirs": ("ux0:app/PSPEMUCFW",),
        "eboots": ("ux0:app/PSPEMUCFW/eboot.bin",),
        "data": ("ux0:pspemu",),
        "staged": ("ux0:Adrenaline.vpk",),
        "repair": REPAIR_STAGE_VPK,
    },
    "retroarch": {
        "name": "RetroArch frontend",
        "app_dirs": ("ux0:app/RETROARCH", "ux0:app/RETROVITA"),
        "eboots": (
            "ux0:app/RETROARCH/eboot.bin",
            "ux0:app/RETROVITA/eboot.bin",
        ),
        "data": ("ux0:data/retroarch",),
        "staged": ("ux0:RetroArch.vpk",),
        "repair": REPAIR_STAGE_VPK,
    },
    "daedalusx64": {
        "name": "DaedalusX64",
        "app_dirs": ("ux0:app/DEDALOX64",),
        "eboots": ("ux0:app/DEDALOX64/eboot.bin",),
        "data": ("ux0:data/DaedalusX64",),
        "staged": ("ux0:DaedalusX64.vpk",),
        "repair": REPAIR_STAGE_VPK,
    },
    "flycast": {
        "name": "Flycast",
        "app_dirs": ("ux0:app/FLYCASTDC",),
        "eboots": ("ux0:app/FLYCASTDC/eboot.bin",),
        "data": (),
        "staged": (),
        "repair": REPAIR_MANUAL,
    },
    "scummvm": {
        "name": "ScummVM",
        "app_dirs": ("ux0:app/VSCU00001",),
        "eboots": ("ux0:app/VSCU00001/eboot.bin",),
        "data": ("ux0:data/scummvm",),
        "staged": (),
        "repair": REPAIR_MANUAL,
    },
    "dsvita": {
        "name": "DSVita",
        "app_dirs": ("ux0:app/DSVITA000",),
        "eboots": ("ux0:app/DSVITA000/eboot.bin",),
        "data": ("ux0:data/dsvita",),
        "staged": ("ux0:dsvita.vpk",),
        "repair": REPAIR_STAGE_VPK,
    },
    "fake-08": {
        "name": "FAKE-08",
        "app_dirs": ("ux0:app/FAKE00008",),
        "eboots": ("ux0:app/FAKE00008/eboot.bin",),
        "data": ("ux0:p8carts",),
        "staged": (),
        "repair": REPAIR_MANUAL,
    },
}


def _normalize_volume(value: str) -> str:
    return value.strip().casefold().rstrip(":/")


def _normalize_vita_path(value: str) -> str:
    raw = value.strip().replace("\\", "/").lstrip("/")
    while "//" in raw:
        raw = raw.replace("//", "/")
    if ":/" in raw:
        volume, rest = raw.split(":/", 1)
        raw = f"{volume}:{rest}"
    return raw.rstrip("/").casefold()


def _existing(evidence: VitaFilesystemEvidence, paths: Iterable[str]) -> tuple[str, ...]:
    return tuple(path for path in paths if evidence.exists(path))


def _basic_app_health(
    evidence: VitaFilesystemEvidence,
    key: str,
) -> VitaComponentHealth:
    rule = _APP_RULES[key]
    name = str(rule["name"])
    repair = str(rule["repair"])
    if not evidence.volume_checked("ux0"):
        return VitaComponentHealth(
            key,
            name,
            UNKNOWN,
            "ux0 was not inspected, so application presence cannot be determined.",
            repair_mode=repair,
        )

    app_dirs = _existing(evidence, rule["app_dirs"])
    eboots = _existing(evidence, rule["eboots"])
    data = _existing(evidence, rule["data"])
    staged = _existing(evidence, rule["staged"])

    if app_dirs and eboots:
        details = list(app_dirs + eboots + data)
        return VitaComponentHealth(
            key,
            name,
            PRESENT_UNVERIFIED,
            "Installed application files are present on ux0, but filesystem evidence cannot prove a successful on-console launch.",
            tuple(details),
            repair,
        )
    if app_dirs:
        return VitaComponentHealth(
            key,
            name,
            PARTIAL,
            "The application directory exists, but the expected executable was not found in the checked evidence.",
            app_dirs + data,
            repair,
        )
    if staged:
        return VitaComponentHealth(
            key,
            name,
            PARTIAL,
            "A VPK is staged on ux0, but a staged package is not evidence that the application is installed. Install it manually with VitaShell.",
            staged,
            repair,
        )
    if data:
        return VitaComponentHealth(
            key,
            name,
            DATA_ONLY,
            "Runtime data or user assets are present, but no installed application directory was found.",
            data,
            repair,
        )
    return VitaComponentHealth(
        key,
        name,
        MISSING,
        "No installed application evidence was found on the inspected ux0 filesystem.",
        repair_mode=repair,
    )


def _retroarch_data_health(evidence: VitaFilesystemEvidence) -> VitaComponentHealth:
    key = "retroarch-data"
    name = "RetroArch data"
    if not evidence.volume_checked("ux0"):
        return VitaComponentHealth(key, name, UNKNOWN, "ux0 was not inspected.")
    if not evidence.exists("ux0:data/retroarch"):
        return VitaComponentHealth(
            key,
            name,
            MISSING,
            "The RetroArch data directory was not found. The official Vita setup requires the companion data payload under ux0:/data/retroarch/.",
            repair_mode=REPAIR_MANUAL,
        )
    markers = _existing(
        evidence,
        (
            "ux0:data/retroarch/assets",
            "ux0:data/retroarch/autoconfig",
            "ux0:data/retroarch/database",
            "ux0:data/retroarch/info",
        ),
    )
    if evidence.exists("ux0:data/retroarch/assets"):
        return VitaComponentHealth(
            key,
            name,
            HEALTHY,
            "RetroArch's data directory and asset tree are present. This is structural data evidence, not a frontend launch test.",
            ("ux0:data/retroarch",) + markers,
            REPAIR_MANUAL,
        )
    return VitaComponentHealth(
        key,
        name,
        PARTIAL,
        "The RetroArch data directory exists, but the expected asset tree was not found. The companion data archive may be incomplete or not yet extracted.",
        ("ux0:data/retroarch",) + markers,
        REPAIR_MANUAL,
    )


def _retroarch_core_health(evidence: VitaFilesystemEvidence) -> VitaComponentHealth:
    key = "retroarch-cores"
    name = "RetroArch cores"
    if not evidence.volume_checked("ux0"):
        return VitaComponentHealth(key, name, UNKNOWN, "ux0 was not inspected.")

    app_roots = tuple(
        path
        for path in ("ux0:app/RETROARCH", "ux0:app/RETROVITA")
        if evidence.exists(path)
    )
    cores: list[str] = []
    for root in app_roots:
        cores.extend(evidence.matching(root, "_libretro.self"))
    cores = sorted(set(cores))

    if cores:
        sample = tuple(cores[:8])
        return VitaComponentHealth(
            key,
            name,
            HEALTHY,
            f"{len(cores)} Vita libretro core executable(s) were found inside the installed RetroArch application tree. Individual game/core compatibility is still launch-tested on the Vita.",
            sample,
            REPAIR_MANUAL,
        )
    if app_roots:
        return VitaComponentHealth(
            key,
            name,
            PARTIAL,
            "RetroArch is present, but no *_libretro.self core executables were found in the checked application tree.",
            app_roots,
            REPAIR_MANUAL,
        )
    return VitaComponentHealth(
        key,
        name,
        MISSING,
        "No installed RetroArch application tree is available to inspect for Vita core executables.",
        repair_mode=REPAIR_MANUAL,
    )


def _libshacccg_health(evidence: VitaFilesystemEvidence) -> VitaComponentHealth:
    key = "libshacccg"
    name = "libshacccg.suprx"
    if not evidence.volume_checked("ur0"):
        return VitaComponentHealth(
            key,
            name,
            UNKNOWN,
            "ur0 was not inspected. A normal ux0-only VitaShell USB mount cannot prove whether the runtime shader compiler is installed.",
            repair_mode=REPAIR_MANUAL,
        )
    if evidence.exists("ur0:data/libshacccg.suprx"):
        return VitaComponentHealth(
            key,
            name,
            HEALTHY,
            "The runtime shader compiler is present at the expected ur0:/data/libshacccg.suprx location.",
            ("ur0:data/libshacccg.suprx",),
            REPAIR_MANUAL,
        )
    if evidence.exists("ur0:data/external/libshacccg.suprx"):
        return VitaComponentHealth(
            key,
            name,
            PARTIAL,
            "A libshacccg copy exists only under ur0:/data/external. The standard runtime location ur0:/data/libshacccg.suprx was not found.",
            ("ur0:data/external/libshacccg.suprx",),
            REPAIR_MANUAL,
        )
    return VitaComponentHealth(
        key,
        name,
        MISSING,
        "libshacccg.suprx was not found in the inspected ur0 data directory. RommHeld will not redistribute or silently install this runtime dependency.",
        repair_mode=REPAIR_MANUAL,
    )


def _active_tai_config(evidence: VitaFilesystemEvidence) -> tuple[str | None, str | None]:
    # taiHEN uses ux0:tai/config.txt when present and falls back to ur0:tai/config.txt.
    if evidence.exists("ux0:tai/config.txt"):
        return "ux0:tai/config.txt", evidence.text("ux0:tai/config.txt")
    if not evidence.volume_checked("ur0"):
        return None, None
    if evidence.exists("ur0:tai/config.txt"):
        return "ur0:tai/config.txt", evidence.text("ur0:tai/config.txt")
    return "", ""


def _kernel_entries(config_text: str) -> tuple[str, ...]:
    entries: list[str] = []
    section = ""
    for raw_line in config_text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("*"):
            section = line.upper()
            continue
        if section == "*KERNEL":
            entries.append(line)
    return tuple(entries)


def _kubridge_health(evidence: VitaFilesystemEvidence) -> VitaComponentHealth:
    key = "kubridge"
    name = "kubridge"
    config_path, config_text = _active_tai_config(evidence)
    if config_path is None:
        return VitaComponentHealth(
            key,
            name,
            UNKNOWN,
            "The active taiHEN configuration could not be determined because ur0 was not inspected and ux0:tai/config.txt is absent.",
            repair_mode=REPAIR_MANUAL,
        )
    if not config_path:
        return VitaComponentHealth(
            key,
            name,
            MISCONFIGURED,
            "Neither ux0:tai/config.txt nor ur0:tai/config.txt exists in the inspected evidence, so kubridge cannot be confirmed as a loaded kernel plugin.",
            repair_mode=REPAIR_MANUAL,
        )
    if config_text is None:
        return VitaComponentHealth(
            key,
            name,
            UNKNOWN,
            f"{config_path} exists, but its contents were not available for read-only inspection.",
            (config_path,),
            REPAIR_MANUAL,
        )

    entries = _kernel_entries(config_text)
    kubridge_entries = tuple(
        entry
        for entry in entries
        if _normalize_vita_path(entry).endswith("/kubridge.skprx")
        or _normalize_vita_path(entry).endswith(":kubridge.skprx")
    )
    if not kubridge_entries:
        visible_file = _existing(
            evidence,
            ("ux0:tai/kubridge.skprx", "ur0:tai/kubridge.skprx"),
        )
        return VitaComponentHealth(
            key,
            name,
            MISCONFIGURED,
            "kubridge is not listed under the active taiHEN *KERNEL section. RommHeld will not rewrite the user's plugin configuration automatically.",
            (config_path,) + visible_file,
            REPAIR_MANUAL,
        )

    entry = kubridge_entries[0]
    normalized_entry = _normalize_vita_path(entry)
    referenced_volume = normalized_entry.split(":", 1)[0]
    if referenced_volume not in {"ux0", "ur0"}:
        return VitaComponentHealth(
            key,
            name,
            MISCONFIGURED,
            f"kubridge is configured under *KERNEL using an unsupported or unrecognized volume path: {entry}",
            (config_path, entry),
            REPAIR_MANUAL,
        )
    if not evidence.volume_checked(referenced_volume):
        return VitaComponentHealth(
            key,
            name,
            UNKNOWN,
            f"kubridge is referenced under *KERNEL at {entry}, but {referenced_volume} was not inspected so the plugin file and version cannot be verified.",
            (config_path, entry),
            REPAIR_MANUAL,
        )
    if not evidence.exists(normalized_entry):
        return VitaComponentHealth(
            key,
            name,
            MISCONFIGURED,
            f"The active *KERNEL section references {entry}, but that plugin file is missing from the inspected filesystem.",
            (config_path, entry),
            REPAIR_MANUAL,
        )
    return VitaComponentHealth(
        key,
        name,
        PRESENT_UNVERIFIED,
        "kubridge is present and referenced by the active taiHEN *KERNEL section. Its binary version is not inferred from the filename, so the DSVita >= 0.3.1 requirement still needs version confirmation on-device or from trusted package metadata.",
        (config_path, entry),
        REPAIR_MANUAL,
    )


def _with_dependency_health(
    app: VitaComponentHealth,
    *,
    dependencies: tuple[VitaComponentHealth, ...],
) -> VitaComponentHealth:
    if app.state != PRESENT_UNVERIFIED:
        return app

    misconfigured = [item for item in dependencies if item.state == MISCONFIGURED]
    missing = [item for item in dependencies if item.state in {MISSING, MANUAL_ONLY}]
    unknown = [item for item in dependencies if item.state == UNKNOWN]
    partial = [item for item in dependencies if item.state == PARTIAL]

    if misconfigured:
        names = ", ".join(item.name for item in misconfigured)
        return VitaComponentHealth(
            app.key,
            app.name,
            MISCONFIGURED,
            f"The application files are present, but required runtime configuration needs attention: {names}.",
            app.evidence + tuple(path for item in misconfigured for path in item.evidence),
            app.repair_mode,
        )
    if missing or partial:
        names = ", ".join(item.name for item in missing + partial)
        return VitaComponentHealth(
            app.key,
            app.name,
            PARTIAL,
            f"The application files are present, but required runtime dependency evidence is incomplete: {names}.",
            app.evidence,
            app.repair_mode,
        )
    if unknown:
        names = ", ".join(item.name for item in unknown)
        return VitaComponentHealth(
            app.key,
            app.name,
            PRESENT_UNVERIFIED,
            f"The application files are present. Launch is not verified, and these dependencies were not checked: {names}.",
            app.evidence,
            app.repair_mode,
        )
    return app


def assess_vita_health(
    evidence: VitaFilesystemEvidence,
) -> dict[str, VitaComponentHealth]:
    """Assess Vita runtime readiness from explicit filesystem/config evidence.

    The assessment never turns a staged VPK into installed-app evidence and never
    treats absence on an unchecked volume as a missing file. Filesystem evidence
    can establish structural readiness, but installed applications remain
    ``Present · launch not verified`` until a real console launch is tested.
    """

    results: dict[str, VitaComponentHealth] = {}
    results["vitashell"] = _basic_app_health(evidence, "vitashell")
    results["retroflow"] = _basic_app_health(evidence, "retroflow")
    results["adrenaline"] = _basic_app_health(evidence, "adrenaline")
    results["retroarch"] = _basic_app_health(evidence, "retroarch")
    results["retroarch-data"] = _retroarch_data_health(evidence)
    results["retroarch-cores"] = _retroarch_core_health(evidence)
    results["libshacccg"] = _libshacccg_health(evidence)
    results["kubridge"] = _kubridge_health(evidence)
    results["daedalusx64"] = _with_dependency_health(
        _basic_app_health(evidence, "daedalusx64"),
        dependencies=(results["libshacccg"],),
    )
    results["flycast"] = _with_dependency_health(
        _basic_app_health(evidence, "flycast"),
        dependencies=(results["libshacccg"], results["kubridge"]),
    )
    results["scummvm"] = _basic_app_health(evidence, "scummvm")
    results["dsvita"] = _with_dependency_health(
        _basic_app_health(evidence, "dsvita"),
        dependencies=(results["libshacccg"], results["kubridge"]),
    )
    results["fake-08"] = _basic_app_health(evidence, "fake-08")
    return results


def inspect_vita_health(
    ux0: Path | None,
    *,
    ur0: Path | None = None,
) -> dict[str, VitaComponentHealth]:
    return assess_vita_health(VitaFilesystemEvidence.from_roots(ux0=ux0, ur0=ur0))


__all__ = [
    "DATA_ONLY",
    "HEALTHY",
    "MANUAL_ONLY",
    "MISCONFIGURED",
    "MISSING",
    "OUTDATED",
    "PARTIAL",
    "PRESENT_UNVERIFIED",
    "REPAIR_MANUAL",
    "REPAIR_NONE",
    "REPAIR_STAGE_VPK",
    "STATE_LABELS",
    "UNKNOWN",
    "VitaComponentHealth",
    "VitaFilesystemEvidence",
    "assess_vita_health",
    "inspect_vita_health",
]
