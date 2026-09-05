from __future__ import annotations

import hashlib
import json
import shutil
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .archive_utils import ArchiveEntry, list_archive
from .config import package_cache_dir
from .transfers import copy_file_chunked


CACHE_DIR = package_cache_dir()
USER_AGENT = "RommHeld/1.0"
RETROARCH_STABLE_VERSION = "1.22.2"


@dataclass(frozen=True)
class PackageSpec:
    key: str
    name: str
    description: str
    source: str
    asset_name: str
    stage_name: str
    destination: str
    sha256: str | None = None
    install_notes: str = ""
    package_type: str = "file"
    archive_destination: str | None = None
    archive_source_prefix: str | None = None
    requires_archive_review: bool = False


PACKAGES = {
    "retroflow": PackageSpec(
        "retroflow", "RetroFlow",
        "Frontend/launcher. It does not provide the emulator cores or RetroAchievements implementation.",
        "github:hamadrehman/RetroFlow-Launcher", "RetroFlow_emu4vita.vpk", "RetroFlow_emu4vita.vpk", "root",
        "839819018f77148ebb2cc497f91edb52a8e6046f16b0871c63f14ea3bc622320",
        "Install the VPK with VitaShell. The current upstream release is the Emu4Vita build.",
    ),
    "adrenaline": PackageSpec(
        "adrenaline", "Adrenaline", "PSP/PS1 environment for the Vita.",
        "github:TheOfficialFloW/Adrenaline", "Adrenaline.vpk", "Adrenaline.vpk", "root", None,
        "Install the VPK with VitaShell. RetroFlow expects the official 6.61 Adrenaline-7 release for PSP/PS1 launching.",
    ),
    "dsvita": PackageSpec(
        "dsvita", "DSVita", "Nintendo DS emulator for Vita.",
        "github:Grarak/DSVita", "dsvita.vpk", "dsvita.vpk", "root",
        "cdf71cb6ef514c7b4f49d532457514f235ddb7129ac0130b9e41270c731ff8a5",
        "Install the VPK with VitaShell. libshacccg.suprx and kubridge >= 0.3.1 are also required. ROMs belong in ux0:/data/dsvita/.",
    ),
    "daedalusx64": PackageSpec(
        "daedalusx64", "DaedalusX64",
        "Vita-native Nintendo 64 emulator. Keep separate from the RetroAchievements-first RetroArch route.",
        "github:Rinnegatamante/DaedalusX64-vitaGL", "DaedalusX64.vpk", "DaedalusX64.vpk", "root", None,
        "Install the Vita-native VPK with VitaShell. RommHeld uses the latest published upstream Vita build and verifies GitHub's SHA-256 asset digest when provided.",
    ),
    "retroarch": PackageSpec(
        "retroarch", "RetroArch",
        "Libretro frontend and core platform. Preferred route for supported RetroAchievements systems.",
        f"direct:https://buildbot.libretro.com/stable/{RETROARCH_STABLE_VERSION}/playstation/vita/RetroArch.vpk",
        "RetroArch.vpk", "RetroArch.vpk", "root", None,
        "Install the VPK with VitaShell. The companion data archive is handled separately.",
    ),
    "retroarch-data": PackageSpec(
        "retroarch-data", "RetroArch data", "RetroArch assets/data package used with the Vita build.",
        f"direct:https://buildbot.libretro.com/stable/{RETROARCH_STABLE_VERSION}/playstation/vita/RetroArch_data.7z",
        "RetroArch_data.7z", "RetroArch_data.7z", "root", None,
        "This is data, not a VPK. Inspect/extract it according to the upstream Vita installation layout.",
        package_type="archive", requires_archive_review=True,
    ),
}


def _request(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def resolve_package(package: PackageSpec) -> tuple[str, str | None]:
    if package.source.startswith("direct:"):
        return package.source.removeprefix("direct:"), package.sha256
    if package.source.startswith("github:"):
        repository = package.source.removeprefix("github:")
        release = json.loads(
            _request(f"https://api.github.com/repos/{repository}/releases/latest").decode(
                "utf-8"
            )
        )
        for asset in release.get("assets", []):
            if asset.get("name") == package.asset_name:
                digest = asset.get("digest")
                if isinstance(digest, str) and digest.startswith("sha256:"):
                    digest = digest.removeprefix("sha256:")
                return asset["browser_download_url"], digest or package.sha256
        raise RuntimeError(
            f"Asset {package.asset_name} was not found in the latest release of {repository}."
        )
    raise RuntimeError(f"Unsupported package source: {package.source}")


def package_path(package: PackageSpec) -> Path:
    return CACHE_DIR / package.stage_name


def download_package(package: PackageSpec, progress=None, cancel_event=None) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError(f"Downloading {package.name} was cancelled.")

    url, digest = resolve_package(package)
    destination = package_path(package)
    temporary = destination.with_suffix(destination.suffix + ".part")

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open(
            "wb"
        ) as output:
            total = int(response.headers.get("Content-Length") or 0)
            completed = 0
            hasher = hashlib.sha256()
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise InterruptedError(f"Downloading {package.name} was cancelled.")
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                hasher.update(chunk)
                completed += len(chunk)
                if progress is not None:
                    progress(completed, total)

        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError(f"Downloading {package.name} was cancelled.")

        actual = hasher.hexdigest()
        if digest and actual.lower() != digest.lower():
            raise IOError(
                f"SHA-256 verification failed for {package.name}: "
                f"expected {digest}, got {actual}"
            )

        temporary.replace(destination)
        return destination
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def inspect_package(package: PackageSpec) -> list[ArchiveEntry]:
    source = package_path(package)
    if not source.is_file():
        raise FileNotFoundError(f"Package has not been downloaded yet: {source}")
    return list_archive(source)


def stage_package(package: PackageSpec, vita: Path, cancel_event=None) -> Path:
    """Safely stage a normal file/VPK. Archive packages must be inspected first."""
    source = package_path(package)
    if not source.is_file():
        raise FileNotFoundError(f"Package has not been downloaded yet: {source}")
    if package.requires_archive_review:
        raise RuntimeError(
            f"{package.name} is an archive package. Inspect its contents before choosing a Vita destination."
        )

    target = (
        vita / package.stage_name
        if package.destination == "root"
        else vita / "data" / package.destination / package.stage_name
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    required = source.stat().st_size
    available = shutil.disk_usage(target.parent).free
    if required > available:
        raise OSError(
            f"Not enough Vita free space to stage {package.name}: "
            f"{required} bytes required, {available} bytes available."
        )

    event = cancel_event if cancel_event is not None else threading.Event()
    if event.is_set() or not copy_file_chunked(source, target, event):
        raise InterruptedError(f"Staging {package.name} was cancelled.")
    final_size = target.stat().st_size
    if final_size != required:
        raise IOError(
            f"Size verification failed while staging {package.name}: "
            f"expected {required} bytes, got {final_size} bytes."
        )
    return target


def get_package(key: str) -> PackageSpec:
    try:
        return PACKAGES[key]
    except KeyError as exc:
        raise KeyError(f"Unknown Vita package: {key}") from exc
