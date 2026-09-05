from __future__ import annotations

from .package_manager import PackageSpec, package_path
from .vita_ftp import VitaFtpBackend, VitaFtpSettings, join_vita_ftp_path


def package_ftp_destination(package: PackageSpec) -> str:
    """Return the ux0-relative destination used when staging a Vita package."""
    if package.requires_archive_review:
        raise RuntimeError(
            f"{package.name} is an archive package and cannot be staged automatically."
        )
    if package.destination == "root":
        return package.stage_name
    return f"data/{package.destination.strip('/')}/{package.stage_name}"


def stage_package_via_ftp(
    package: PackageSpec,
    settings: VitaFtpSettings,
    *,
    cancel_event=None,
    progress=None,
    backend_factory=VitaFtpBackend,
) -> tuple[str, str]:
    """Stage one verified package through VitaShell FTP without coupling package prep to transport."""
    source = package_path(package)
    if not source.is_file():
        raise FileNotFoundError(f"Package has not been downloaded yet: {source}")

    destination = package_ftp_destination(package)
    backend = backend_factory(settings)
    try:
        backend.connect()
        result, _ = backend.upload(
            source,
            destination,
            overwrite=True,
            cancel_event=cancel_event,
            progress=progress,
        )
    finally:
        backend.close()

    display_path = join_vita_ftp_path(settings.remote_root, destination).removeprefix("/")
    return result, display_path


__all__ = ["package_ftp_destination", "stage_package_via_ftp"]
