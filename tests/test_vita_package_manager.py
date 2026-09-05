from pathlib import Path

from romm_vita_manager import package_manager
from romm_vita_manager.config import package_cache_dir
from romm_vita_manager.emulators import EMULATORS, detect_emulators
from romm_vita_manager.package_manager import (
    PACKAGES,
    RETROARCH_STABLE_VERSION,
    PackageSpec,
    stage_package,
)


def test_vita_packages_use_platform_cache_directory():
    assert package_manager.CACHE_DIR == package_cache_dir()
    assert package_manager.CACHE_DIR.name == "packages"


def test_retroarch_uses_current_stable_vita_build():
    assert RETROARCH_STABLE_VERSION == "1.22.2"
    assert f"/stable/{RETROARCH_STABLE_VERSION}/playstation/vita/RetroArch.vpk" in PACKAGES["retroarch"].source
    assert f"/stable/{RETROARCH_STABLE_VERSION}/playstation/vita/RetroArch_data.7z" in PACKAGES["retroarch-data"].source
    assert PACKAGES["retroarch-data"].requires_archive_review is True


def test_retroarch_app_and_data_are_separate_setup_components(tmp_path: Path):
    definitions = {definition.key: definition for definition in EMULATORS}
    assert definitions["retroarch"].package_keys == ("retroarch",)
    assert definitions["retroarch-data"].package_keys == ("retroarch-data",)

    (tmp_path / "data" / "retroarch").mkdir(parents=True)
    detected = detect_emulators(tmp_path)

    assert detected["retroarch"] is False
    assert detected["retroarch-data"] is True


def test_daedalus_uses_vita_native_upstream_vpk():
    package = PACKAGES["daedalusx64"]

    assert package.source == "github:Rinnegatamante/DaedalusX64-vitaGL"
    assert package.asset_name == "DaedalusX64.vpk"
    assert package.stage_name == "DaedalusX64.vpk"
    assert package.requires_archive_review is False


def test_daedalus_title_id_is_detected(tmp_path: Path):
    (tmp_path / "app" / "DEDALOX64").mkdir(parents=True)

    detected = detect_emulators(tmp_path)

    assert detected["daedalusx64"] is True


def test_dsvita_title_id_is_detected(tmp_path: Path):
    (tmp_path / "app" / "DSVITA000").mkdir(parents=True)

    detected = detect_emulators(tmp_path)

    assert detected["dsvita"] is True


def test_dsvita_rom_directory_does_not_claim_emulator_is_installed(tmp_path: Path):
    (tmp_path / "data" / "dsvita").mkdir(parents=True)

    detected = detect_emulators(tmp_path)

    assert detected["dsvita"] is False


def test_retroarch_vita_title_id_is_detected(tmp_path: Path):
    (tmp_path / "app" / "RETROVITA").mkdir(parents=True)

    detected = detect_emulators(tmp_path)

    assert detected["retroarch"] is True


def test_retroarch_data_directory_does_not_claim_app_is_installed(tmp_path: Path):
    (tmp_path / "data" / "retroarch").mkdir(parents=True)

    detected = detect_emulators(tmp_path)

    assert detected["retroarch"] is False
    assert detected["retroarch-data"] is True


def test_additional_vita_runtime_title_ids_are_detected(tmp_path: Path):
    for title_id, key in (
        ("FLYCASTDC", "flycast"),
        ("VSCU00001", "scummvm"),
        ("FAKE00008", "fake-08"),
    ):
        vita = tmp_path / key
        (vita / "app" / title_id).mkdir(parents=True)

        detected = detect_emulators(vita)

        assert detected[key] is True


def test_stage_package_replaces_existing_file_after_safe_copy(monkeypatch, tmp_path: Path):
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(package_manager, "CACHE_DIR", cache)
    package = PackageSpec(
        key="test",
        name="Test VPK",
        description="test",
        source="direct:https://example.invalid/test.vpk",
        asset_name="test.vpk",
        stage_name="test.vpk",
        destination="root",
    )
    source = cache / "test.vpk"
    source.write_bytes(b"new-package-content")
    vita = tmp_path / "vita"
    vita.mkdir()
    target = vita / "test.vpk"
    target.write_bytes(b"old")

    staged = stage_package(package, vita)

    assert staged == target
    assert target.read_bytes() == b"new-package-content"
    assert not list(vita.glob(".*.rommheld-*.part"))


def test_archive_package_is_never_staged_blindly(monkeypatch, tmp_path: Path):
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(package_manager, "CACHE_DIR", cache)
    package = PackageSpec(
        key="archive",
        name="Archive",
        description="test",
        source="direct:https://example.invalid/archive.zip",
        asset_name="archive.zip",
        stage_name="archive.zip",
        destination="root",
        requires_archive_review=True,
    )
    (cache / "archive.zip").write_bytes(b"archive")
    vita = tmp_path / "vita"
    vita.mkdir()

    try:
        stage_package(package, vita)
    except RuntimeError as exc:
        assert "Inspect its contents" in str(exc)
    else:
        raise AssertionError("archive package should not be staged")
