from __future__ import annotations

from pathlib import Path

from romm_vita_manager.models import Game
from romm_vita_manager.vita_library_support import (
    copy_job_target,
    required_usb_batch_space,
)


def game(path: Path, size: int, *, name: str = "Game", platform: str = "snes") -> Game:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return Game(
        path=path,
        name=name,
        source_platform=platform,
        size=size,
        relative=Path(path.name),
    )


def job(item: Game, destination: Path, mode: str = "file"):
    return (item, destination, mode, "Target")


def test_new_files_require_their_full_cumulative_batch_size(tmp_path: Path) -> None:
    first = game(tmp_path / "source" / "first.bin", 100, name="First")
    second = game(tmp_path / "source" / "second.bin", 200, name="Second")
    destination = tmp_path / "vita" / "roms"

    assert required_usb_batch_space([
        job(first, destination),
        job(second, destination),
    ]) == 300


def test_replacements_require_peak_staging_headroom_not_sum_of_sources(tmp_path: Path) -> None:
    first = game(tmp_path / "source" / "first.bin", 100, name="First")
    second = game(tmp_path / "source" / "second.bin", 200, name="Second")
    destination = tmp_path / "vita" / "roms"
    destination.mkdir(parents=True)
    (destination / "first.bin").write_bytes(b"o" * 90)
    (destination / "second.bin").write_bytes(b"o" * 190)

    assert required_usb_batch_space([
        job(first, destination),
        job(second, destination),
    ]) == 210


def test_shrinking_replacements_release_space_for_later_jobs(tmp_path: Path) -> None:
    first = game(tmp_path / "source" / "first.bin", 100, name="First")
    second = game(tmp_path / "source" / "second.bin", 300, name="Second")
    destination = tmp_path / "vita" / "roms"
    destination.mkdir(parents=True)
    (destination / "first.bin").write_bytes(b"o" * 200)
    (destination / "second.bin").write_bytes(b"o" * 400)

    assert required_usb_batch_space([
        job(first, destination),
        job(second, destination),
    ]) == 200


def test_mixed_batch_accounts_for_space_permanently_consumed_by_new_files(tmp_path: Path) -> None:
    new_item = game(tmp_path / "source" / "new.bin", 100, name="New")
    replacement = game(tmp_path / "source" / "replacement.bin", 200, name="Replacement")
    destination = tmp_path / "vita" / "roms"
    destination.mkdir(parents=True)
    (destination / "replacement.bin").write_bytes(b"o" * 150)

    assert required_usb_batch_space([
        job(new_item, destination),
        job(replacement, destination),
    ]) == 300


def test_same_size_job_needs_no_additional_storage(tmp_path: Path) -> None:
    item = game(tmp_path / "source" / "same.bin", 128)
    destination = tmp_path / "vita" / "roms"
    destination.mkdir(parents=True)
    (destination / "same.bin").write_bytes(b"o" * 128)

    assert required_usb_batch_space([job(item, destination)]) == 0


def test_game_folder_jobs_use_the_same_target_as_copy_worker(tmp_path: Path) -> None:
    source = tmp_path / "source" / "SLUS01234" / "EBOOT.PBP"
    item = game(source, 256, name="Friendly Name", platform="ps1")
    destination = tmp_path / "vita" / "pspemu" / "PSP" / "GAME"
    target = destination / "SLUS01234" / "EBOOT.PBP"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"o" * 200)

    assert copy_job_target(item, destination, "game-folder") == target
    assert required_usb_batch_space([job(item, destination, "game-folder")]) == 256
