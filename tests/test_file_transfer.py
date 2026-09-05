from pathlib import Path

from romm_vita_manager.file_transfer import required_transfer_space


def test_new_transfer_requires_full_source_size(tmp_path: Path):
    assert required_transfer_space(1024, tmp_path / "new.bin") == 1024


def test_same_size_destination_requires_no_space(tmp_path: Path):
    destination = tmp_path / "same.bin"
    destination.write_bytes(b"abcd")

    assert required_transfer_space(4, destination) == 0
    assert required_transfer_space(4, destination, overwrite=True) == 0


def test_different_destination_requires_no_space_before_overwrite_approval(tmp_path: Path):
    destination = tmp_path / "different.bin"
    destination.write_bytes(b"old")

    assert required_transfer_space(8, destination, overwrite=False) == 0


def test_approved_overwrite_requires_full_staging_space(tmp_path: Path):
    destination = tmp_path / "different.bin"
    destination.write_bytes(b"old")

    assert required_transfer_space(8, destination, overwrite=True) == 8
