from pathlib import Path
import zipfile

import pytest

from romm_vita_manager.three_ds_filesystem_worker import ThreeDSFilesystemTransferWorker
from romm_vita_manager.three_ds_payload import (
    planned_payload_filename,
    raw_payload_supported_for_file,
    resolve_target_payload,
)


def _zip(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def _validated_3ds_root(tmp_path: Path) -> Path:
    root = tmp_path / "sd"
    root.mkdir()
    (root / "boot.firm").write_bytes(b"firm")
    (root / "boot.3dsx").write_bytes(b"3dsx")
    (root / "luma").mkdir()
    return root


def test_open_agb_zip_resolves_single_gba_payload(tmp_path: Path):
    archive = _zip(
        tmp_path / "Advance Wars (USA) (Rev 1).zip",
        {
            "README.txt": b"metadata",
            "Advance Wars (USA) (Rev 1).gba": b"gba payload",
        },
    )
    workspace = tmp_path / "work"
    workspace.mkdir()

    payload = resolve_target_payload(archive, "open_agb_firm", "gba", workspace)

    assert payload.name == "Advance Wars (USA) (Rev 1).gba"
    assert payload.read_bytes() == b"gba payload"


def test_raw_runtime_archive_with_multiple_roms_fails_closed(tmp_path: Path):
    archive = _zip(
        tmp_path / "collection.zip",
        {
            "first.gba": b"one",
            "second.gba": b"two",
        },
    )
    workspace = tmp_path / "work"
    workspace.mkdir()

    with pytest.raises(ValueError, match="multiple compatible ROM payloads"):
        resolve_target_payload(archive, "open_agb_firm", "gba", workspace)


def test_raw_runtime_archive_without_expected_rom_fails_closed(tmp_path: Path):
    archive = _zip(tmp_path / "wrong.zip", {"wrong.gb": b"gb"})
    workspace = tmp_path / "work"
    workspace.mkdir()

    with pytest.raises(ValueError, match="does not contain a compatible gba ROM"):
        resolve_target_payload(archive, "open_agb_firm", "gba", workspace)


def test_direct_raw_payload_passes_through_unchanged(tmp_path: Path):
    source = tmp_path / "game.gba"
    source.write_bytes(b"gba")
    workspace = tmp_path / "work"
    workspace.mkdir()

    assert resolve_target_payload(source, "open_agb_firm", "gba", workspace) == source


def test_retroarch_keeps_zip_content_as_supplied(tmp_path: Path):
    archive = _zip(tmp_path / "game.zip", {"game.gba": b"gba"})
    workspace = tmp_path / "work"
    workspace.mkdir()

    assert resolve_target_payload(archive, "retroarch", "gba", workspace) == archive


def test_unsupported_7z_raw_route_is_not_advertised_as_preparable(tmp_path: Path):
    archive = tmp_path / "game.7z"
    archive.write_bytes(b"not a real archive")
    workspace = tmp_path / "work"
    workspace.mkdir()

    assert not raw_payload_supported_for_file("open_agb_firm", "gba", archive.name)
    with pytest.raises(ValueError, match="cannot yet be safely extracted"):
        resolve_target_payload(archive, "open_agb_firm", "gba", workspace)


def test_n64_archive_preserves_the_actual_single_rom_extension(tmp_path: Path):
    archive = _zip(tmp_path / "Mario Kart 64.zip", {"Mario Kart 64.v64": b"n64"})
    workspace = tmp_path / "work"
    workspace.mkdir()

    payload = resolve_target_payload(archive, "daedalusx64", "n64", workspace)

    assert payload.name == "Mario Kart 64.v64"
    assert planned_payload_filename("daedalusx64", "n64", archive.name) is None


def test_single_suffix_archive_has_raw_destination_preview():
    assert planned_payload_filename(
        "open_agb_firm",
        "gba",
        "Advance Wars (USA) (Rev 1).zip",
    ) == "Advance Wars (USA) (Rev 1).gba"


def test_local_mounted_sd_worker_extracts_gba_zip_before_copy(tmp_path: Path):
    source = _zip(
        tmp_path / "Advance Wars (USA) (Rev 1).zip",
        {"Advance Wars (USA) (Rev 1).gba": b"real gba bytes"},
    )
    root = _validated_3ds_root(tmp_path)
    destinations: list[str] = []
    results: list[str] = []
    failures: list[str] = []

    worker = ThreeDSFilesystemTransferWorker(
        "sd",
        target_key="open_agb_firm",
        platform_slug="gba",
        original_filename=source.name,
        source=source,
        storage_root=root,
    )
    worker.destination_resolved.connect(destinations.append)
    worker.completed.connect(results.append)
    worker.failed.connect(failures.append)
    worker.run()

    expected = root / "roms" / "gba" / "Advance Wars (USA) (Rev 1).gba"
    assert failures == []
    assert results == ["copied"]
    assert destinations == ["/roms/gba/Advance Wars (USA) (Rev 1).gba"]
    assert expected.read_bytes() == b"real gba bytes"
    assert not (root / "roms" / "gba" / source.name).exists()
