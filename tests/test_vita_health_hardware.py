from __future__ import annotations

from romm_vita_manager.vita_health import (
    HEALTHY,
    MISCONFIGURED,
    OUTDATED,
    PRESENT_UNVERIFIED,
    UNKNOWN,
    VitaFilesystemEvidence,
    assess_vita_health,
)
from romm_vita_manager.vita_health_hardware import (
    VitaHardwareEvidence,
    apply_vita_hardware_evidence,
)


def _filesystem(*paths: str, checked=("ux0",), text_files=None):
    return assess_vita_health(
        VitaFilesystemEvidence.from_paths(
            paths,
            checked_volumes=checked,
            text_files=text_files,
        )
    )


def test_verified_real_device_launch_promotes_app_to_healthy() -> None:
    health = _filesystem(
        "ux0:app/RETROARCH",
        "ux0:app/RETROARCH/eboot.bin",
    )
    assert health["retroarch"].state == PRESENT_UNVERIFIED

    result = apply_vita_hardware_evidence(
        health,
        VitaHardwareEvidence.from_observations(
            verified_components=("retroarch",),
        ),
    )

    assert result["retroarch"].state == HEALTHY
    assert "real Vita hardware" in result["retroarch"].summary
    assert "hardware:verified:retroarch" in result["retroarch"].evidence


def test_verified_component_can_resolve_uninspected_filesystem_uncertainty() -> None:
    health = _filesystem()
    assert health["libshacccg"].state == UNKNOWN

    result = apply_vita_hardware_evidence(
        health,
        VitaHardwareEvidence.from_observations(
            verified_components=("libshacccg",),
        ),
    )

    assert result["libshacccg"].state == HEALTHY


def test_trusted_old_kubridge_version_is_outdated() -> None:
    health = _filesystem(
        "ur0:tai/config.txt",
        "ur0:tai/kubridge.skprx",
        checked=("ux0", "ur0"),
        text_files={"ur0:tai/config.txt": "*KERNEL\nur0:tai/kubridge.skprx\n"},
    )

    result = apply_vita_hardware_evidence(
        health,
        VitaHardwareEvidence.from_observations(
            trusted_versions={"kubridge": "0.3.0"},
        ),
    )

    assert result["kubridge"].state == OUTDATED
    assert "0.3.1 or later" in result["kubridge"].summary


def test_trusted_supported_kubridge_version_satisfies_version_requirement() -> None:
    health = _filesystem(
        "ur0:tai/config.txt",
        "ur0:tai/kubridge.skprx",
        checked=("ux0", "ur0"),
        text_files={"ur0:tai/config.txt": "*KERNEL\nur0:tai/kubridge.skprx\n"},
    )

    result = apply_vita_hardware_evidence(
        health,
        VitaHardwareEvidence.from_observations(
            trusted_versions={"kubridge": "v0.3.1"},
        ),
    )

    assert result["kubridge"].state == HEALTHY
    assert ">= 0.3.1" in result["kubridge"].summary


def test_version_evidence_does_not_hide_taihen_misconfiguration() -> None:
    health = _filesystem(
        "ur0:tai/config.txt",
        "ur0:tai/kubridge.skprx",
        checked=("ux0", "ur0"),
        text_files={"ur0:tai/config.txt": "*KERNEL\nur0:tai/other.skprx\n"},
    )
    assert health["kubridge"].state == MISCONFIGURED

    result = apply_vita_hardware_evidence(
        health,
        VitaHardwareEvidence.from_observations(
            trusted_versions={"kubridge": "0.3.1"},
        ),
    )

    assert result["kubridge"].state == MISCONFIGURED


def test_unparseable_version_never_creates_outdated_claim() -> None:
    health = _filesystem(
        "ur0:tai/config.txt",
        "ur0:tai/kubridge.skprx",
        checked=("ux0", "ur0"),
        text_files={"ur0:tai/config.txt": "*KERNEL\nur0:tai/kubridge.skprx\n"},
    )

    result = apply_vita_hardware_evidence(
        health,
        VitaHardwareEvidence.from_observations(
            trusted_versions={"kubridge": "unknown-build"},
        ),
    )

    assert result["kubridge"].state == PRESENT_UNVERIFIED
