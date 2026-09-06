from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .config import package_cache_dir
from .storage_validation import validate_3ds_sd


USER_AGENT = "RommHeld/3DS-Package-Staging"
MAX_PACKAGE_BYTES = 32 * 1024 * 1024
BACKUP_SUFFIX = ".rommheld.bak"


@dataclass(frozen=True)
class ThreeDSPackageSpec:
    key: str
    app_key: str
    name: str
    repository: str
    asset_name: str
    destination: str
    description: str


@dataclass(frozen=True)
class ResolvedThreeDSPackage:
    spec: ThreeDSPackageSpec
    version: str
    url: str
    size: int
    sha256: str | None


PACKAGES: dict[str, ThreeDSPackageSpec] = {
    "ftpd-3dsx": ThreeDSPackageSpec(
        "ftpd-3dsx",
        "ftpd",
        "ftpd",
        "mtheall/ftpd",
        "ftpd.3dsx",
        "3ds/ftpd/ftpd.3dsx",
        "FTP server used for RommHeld live filesystem transfers.",
    ),
    "universal-updater-3dsx": ThreeDSPackageSpec(
        "universal-updater-3dsx",
        "universal-updater",
        "Universal-Updater",
        "Universal-Team/Universal-Updater",
        "Universal-Updater.3dsx",
        "3ds/Universal-Updater.3dsx",
        "On-device installer/updater used for broader 3DS homebrew management.",
    ),
    "red-viper-3dsx": ThreeDSPackageSpec(
        "red-viper-3dsx",
        "red-viper",
        "Red Viper",
        "skyfloogle/red-viper",
        "red-viper.3dsx",
        "3ds/RedViper/RedViper.3dsx",
        "Dedicated Virtual Boy emulator for the Nintendo 3DS.",
    ),
    "fbi-3dsx": ThreeDSPackageSpec(
        "fbi-3dsx",
        "fbi",
        "FBI",
        "Steveice10/FBI",
        "FBI.3dsx",
        "3ds/FBI/FBI.3dsx",
        "Homebrew Launcher build of FBI used to bootstrap CIA and Remote Install workflows.",
    ),
    "checkpoint-3dsx": ThreeDSPackageSpec(
        "checkpoint-3dsx",
        "checkpoint",
        "Checkpoint",
        "BernardoGiordano/Checkpoint",
        "Checkpoint.3dsx",
        "3ds/Checkpoint/Checkpoint.3dsx",
        "Save manager used for backups before title/runtime changes.",
    ),
}


PACKAGE_FOR_APP = {
    "ftpd": "ftpd-3dsx",
    "universal-updater": "universal-updater-3dsx",
    "red-viper": "red-viper-3dsx",
    "fbi": "fbi-3dsx",
    "checkpoint": "checkpoint-3dsx",
}


def get_package(key: str) -> ThreeDSPackageSpec:
    try:
        return PACKAGES[key]
    except KeyError as exc:
        raise KeyError(f"Unknown 3DS package: {key}") from exc


def package_for_app(app_key: str) -> ThreeDSPackageSpec | None:
    package_key = PACKAGE_FOR_APP.get(app_key)
    return PACKAGES.get(package_key) if package_key else None


def _request_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub returned an invalid release response.")
    return payload


def _release_digest(asset: dict) -> str | None:
    digest = asset.get("digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        return None
    value = digest.removeprefix("sha256:").strip().lower()
    return value if len(value) == 64 else None


def resolve_package(spec: ThreeDSPackageSpec) -> ResolvedThreeDSPackage:
    release = _request_json(
        f"https://api.github.com/repos/{spec.repository}/releases/latest"
    )
    if release.get("draft") or release.get("prerelease"):
        raise RuntimeError(f"Latest {spec.name} release is not a stable published release.")
    version = str(release.get("tag_name") or release.get("name") or "latest")
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError(f"Latest {spec.name} release has no asset list.")

    asset = next(
        (
            item
            for item in assets
            if isinstance(item, dict) and item.get("name") == spec.asset_name
        ),
        None,
    )
    if asset is None:
        raise RuntimeError(
            f"Latest {spec.name} release does not contain {spec.asset_name}."
        )
    url = str(asset.get("browser_download_url") or "")
    size = int(asset.get("size") or 0)
    if not url.startswith("https://github.com/"):
        raise RuntimeError(f"Unexpected download host for {spec.name}.")
    if size <= 0 or size > MAX_PACKAGE_BYTES:
        raise RuntimeError(
            f"Unexpected {spec.name} package size: {size} bytes. Refusing automatic staging."
        )
    return ResolvedThreeDSPackage(
        spec=spec,
        version=version,
        url=url,
        size=size,
        sha256=_release_digest(asset),
    )


def package_cache_path(resolved: ResolvedThreeDSPackage) -> Path:
    root = package_cache_dir() / "three-ds"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{resolved.spec.key}-{resolved.version}-{resolved.spec.asset_name}"


def download_package(
    resolved: ResolvedThreeDSPackage,
    *,
    progress=None,
    cancel_event=None,
) -> Path:
    destination = package_cache_path(resolved)
    temporary = destination.with_name(destination.name + ".part")
    request = urllib.request.Request(
        resolved.url,
        headers={"User-Agent": USER_AGENT},
    )
    completed = 0
    hasher = hashlib.sha256()
    try:
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("3DS package download cancelled.")
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise InterruptedError("3DS package download cancelled.")
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                completed += len(chunk)
                if completed > MAX_PACKAGE_BYTES:
                    raise IOError("3DS package exceeded the maximum allowed download size.")
                output.write(chunk)
                hasher.update(chunk)
                if progress is not None:
                    progress(completed, resolved.size)

        if completed != resolved.size:
            raise IOError(
                f"Downloaded {resolved.spec.name} size mismatch: expected {resolved.size}, got {completed}."
            )
        actual_digest = hasher.hexdigest()
        if resolved.sha256 and actual_digest.lower() != resolved.sha256.lower():
            raise IOError(
                f"SHA-256 verification failed for {resolved.spec.name}: expected {resolved.sha256}, got {actual_digest}."
            )
        temporary.replace(destination)
        return destination
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def validate_staging_root(sd_root: Path) -> Path:
    root = sd_root.expanduser().resolve()
    validation = validate_3ds_sd(root)
    if validation.confidence != "high":
        raise ValueError(
            "Automatic homebrew staging requires a high-confidence Nintendo 3DS SD-card root."
        )
    return root


def stage_package(
    resolved: ResolvedThreeDSPackage,
    downloaded: Path,
    sd_root: Path,
) -> Path:
    source = downloaded.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Downloaded 3DS package does not exist: {source}")
    if source.stat().st_size != resolved.size:
        raise IOError(
            f"Cached {resolved.spec.name} size mismatch: expected {resolved.size}, got {source.stat().st_size}."
        )
    if resolved.sha256:
        actual = hashlib.sha256(source.read_bytes()).hexdigest()
        if actual.lower() != resolved.sha256.lower():
            raise IOError(
                f"Cached {resolved.spec.name} failed SHA-256 verification before staging."
            )

    root = validate_staging_root(sd_root)
    target = root / resolved.spec.destination
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = target.with_name(target.name + BACKUP_SUFFIX)
    temporary = target.with_name(target.name + ".rommheld.tmp")

    try:
        if target.exists() and not backup.exists():
            shutil.copy2(target, backup)
        shutil.copy2(source, temporary)
        if temporary.stat().st_size != resolved.size:
            raise IOError(f"Staged {resolved.spec.name} failed size verification.")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target
