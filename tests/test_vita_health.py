from __future__ import annotations

from pathlib import Path

from romm_vita_manager.vita_health import (
    DATA_ONLY,
    HEALTHY,
    MISCONFIGURED,
    MISSING,
    PARTIAL,
    PRESENT_UNVERIFIED,
    UNKNOWN,
    VitaFilesystemEvidence,
    assess_vita_health,
    inspect_vita_health,
)


def _evidence(
    *paths: str,
    checked=("ux0",),
    text_files: dict[str, str] | None = None,
) -> VitaFilesystemEvidence:
    return VitaFilesystemEvidence.from_paths(
        paths,
        checked_volumes=checked,
        text_files=text_files,
    )


def test_staged_vpk_never_counts_as_installed_application() -> None:
    health = assess_vita_health(_evidence("ux0:RetroArch.vpk"))

    assert health["retroarch"].state == PARTIAL
    assert "staged" in health["retroarch"].summary.lower()
    assert "not evidence" in health["retroarch"].summary.lower()


def test_installed_application_files_remain_launch_unverified() -> None:
    health = assess_vita_health(
        _evidence(
            "ux0:app/RETROFLOW",
            "ux0:app/RETROFLOW/eboot.bin",
            "ux0:data/RetroFlow",
        )
    )

    assert health["retroflow"].state == PRESENT_UNVERIFIED
    assert health["retroflow"].label == "Present · launch not verified"


def test_data_without_frontend_is_reported_as_data_only() -> None:
    health = assess_vita_health(_evidence("ux0:data/retroarch", "ux0:data/retroarch/assets"))

    assert health["retroarch"].state == DATA_ONLY
    assert health["retroarch-data"].state == HEALTHY


def test_retroarch_data_directory_without_assets_is_partial() -> None:
    health = assess_vita_health(_evidence("ux0:data/retroarch"))

    assert health["retroarch-data"].state == PARTIAL


def test_retroarch_core_inventory_uses_vita_static_core_executables() -> None:
    health = assess_vita_health(
        _evidence(
            "ux0:app/RETROARCH",
            "ux0:app/RETROARCH/eboot.bin",
            "ux0:app/RETROARCH/fceumm_libretro.self",
            "ux0:app/RETROARCH/snes9x2005_libretro.self",
        )
    )

    assert health["retroarch-cores"].state == HEALTHY
    assert "2 Vita libretro core executable" in health["retroarch-cores"].summary


def test_retroarch_frontend_without_cores_is_partial_core_state() -> None:
    health = assess_vita_health(
        _evidence("ux0:app/RETROVITA", "ux0:app/RETROVITA/eboot.bin")
    )

    assert health["retroarch"].state == PRESENT_UNVERIFIED
    assert health["retroarch-cores"].state == PARTIAL


def test_ux0_only_inspection_does_not_claim_ur0_dependencies_are_missing() -> None:
    health = assess_vita_health(
        _evidence("ux0:app/DSVITA000", "ux0:app/DSVITA000/eboot.bin")
    )

    assert health["libshacccg"].state == UNKNOWN
    assert health["kubridge"].state == UNKNOWN
    assert health["dsvita"].state == PRESENT_UNVERIFIED
    assert "not checked" in health["dsvita"].summary.lower()


def test_libshacccg_expected_ur0_location_is_structurally_healthy() -> None:
    health = assess_vita_health(
        _evidence("ur0:data/libshacccg.suprx", checked=("ux0", "ur0"))
    )

    assert health["libshacccg"].state == HEALTHY


def test_libshacccg_external_only_copy_is_partial() -> None:
    health = assess_vita_health(
        _evidence("ur0:data/external/libshacccg.suprx", checked=("ux0", "ur0"))
    )

    assert health["libshacccg"].state == PARTIAL


def test_taihen_ux0_config_takes_precedence_and_can_verify_kubridge_structure() -> None:
    config = """
*KERNEL
ux0:tai/kubridge.skprx
*ALL
ux0:tai/example.suprx
"""
    health = assess_vita_health(
        _evidence(
            "ux0:tai/config.txt",
            "ux0:tai/kubridge.skprx",
            "ur0:tai/config.txt",
            checked=("ux0", "ur0"),
            text_files={
                "ux0:tai/config.txt": config,
                "ur0:tai/config.txt": "*KERNEL\nur0:tai/other.skprx\n",
            },
        )
    )

    assert health["kubridge"].state == PRESENT_UNVERIFIED
    assert "version is not" in health["kubridge"].summary.lower()


def test_kubridge_file_without_kernel_entry_is_misconfigured() -> None:
    health = assess_vita_health(
        _evidence(
            "ur0:tai/config.txt",
            "ur0:tai/kubridge.skprx",
            checked=("ux0", "ur0"),
            text_files={"ur0:tai/config.txt": "*KERNEL\nur0:tai/other.skprx\n"},
        )
    )

    assert health["kubridge"].state == MISCONFIGURED
    assert "will not rewrite" in health["kubridge"].summary.lower()


def test_kubridge_config_reference_to_missing_plugin_is_misconfigured() -> None:
    health = assess_vita_health(
        _evidence(
            "ur0:tai/config.txt",
            checked=("ux0", "ur0"),
            text_files={"ur0:tai/config.txt": "*KERNEL\nur0:tai/kubridge.skprx\n"},
        )
    )

    assert health["kubridge"].state == MISCONFIGURED
    assert "plugin file is missing" in health["kubridge"].summary.lower()


def test_ur0_kubridge_reference_remains_not_checked_when_only_ux0_is_visible() -> None:
    health = assess_vita_health(
        _evidence(
            "ux0:tai/config.txt",
            checked=("ux0",),
            text_files={"ux0:tai/config.txt": "*KERNEL\nur0:tai/kubridge.skprx\n"},
        )
    )

    assert health["kubridge"].state == UNKNOWN


def test_dsvita_reports_misconfigured_when_kubridge_kernel_entry_is_wrong() -> None:
    health = assess_vita_health(
        _evidence(
            "ux0:app/DSVITA000",
            "ux0:app/DSVITA000/eboot.bin",
            "ur0:data/libshacccg.suprx",
            "ur0:tai/config.txt",
            "ur0:tai/kubridge.skprx",
            checked=("ux0", "ur0"),
            text_files={"ur0:tai/config.txt": "*KERNEL\nur0:tai/other.skprx\n"},
        )
    )

    assert health["dsvita"].state == MISCONFIGURED


def test_dsvita_with_structural_prerequisites_still_does_not_claim_launch_health() -> None:
    health = assess_vita_health(
        _evidence(
            "ux0:app/DSVITA000",
            "ux0:app/DSVITA000/eboot.bin",
            "ur0:data/libshacccg.suprx",
            "ur0:tai/config.txt",
            "ur0:tai/kubridge.skprx",
            checked=("ux0", "ur0"),
            text_files={"ur0:tai/config.txt": "*KERNEL\nur0:tai/kubridge.skprx\n"},
        )
    )

    assert health["dsvita"].state == PRESENT_UNVERIFIED
    assert health["libshacccg"].state == HEALTHY
    assert health["kubridge"].state == PRESENT_UNVERIFIED


def test_flycast_inherits_missing_runtime_dependency_as_partial() -> None:
    health = assess_vita_health(
        _evidence(
            "ux0:app/FLYCASTDC",
            "ux0:app/FLYCASTDC/eboot.bin",
            "ur0:tai/config.txt",
            "ur0:tai/kubridge.skprx",
            checked=("ux0", "ur0"),
            text_files={"ur0:tai/config.txt": "*KERNEL\nur0:tai/kubridge.skprx\n"},
        )
    )

    assert health["libshacccg"].state == MISSING
    assert health["flycast"].state == PARTIAL


def test_scummvm_and_fake08_data_do_not_claim_app_installation() -> None:
    health = assess_vita_health(
        _evidence("ux0:data/scummvm", "ux0:p8carts")
    )

    assert health["scummvm"].state == DATA_ONLY
    assert health["fake-08"].state == DATA_ONLY


def test_from_roots_reads_only_targeted_taihen_text_and_runtime_markers(tmp_path: Path) -> None:
    ux0 = tmp_path / "ux0"
    ur0 = tmp_path / "ur0"
    (ux0 / "app" / "DSVITA000").mkdir(parents=True)
    (ux0 / "app" / "DSVITA000" / "eboot.bin").write_bytes(b"app")
    (ur0 / "data").mkdir(parents=True)
    (ur0 / "data" / "libshacccg.suprx").write_bytes(b"runtime")
    (ur0 / "tai").mkdir(parents=True)
    (ur0 / "tai" / "kubridge.skprx").write_bytes(b"plugin")
    (ur0 / "tai" / "config.txt").write_text(
        "*KERNEL\nur0:tai/kubridge.skprx\n",
        encoding="utf-8",
    )
    # User data exists but is intentionally outside the targeted evidence probes.
    (ux0 / "data" / "private-game").mkdir(parents=True)
    (ux0 / "data" / "private-game" / "save.dat").write_bytes(b"secret")

    evidence = VitaFilesystemEvidence.from_roots(ux0=ux0, ur0=ur0)
    health = inspect_vita_health(ux0, ur0=ur0)

    assert evidence.volume_checked("ux0")
    assert evidence.volume_checked("ur0")
    assert not any("private-game" in path for path in evidence.paths)
    assert health["dsvita"].state == PRESENT_UNVERIFIED
