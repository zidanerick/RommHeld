from pathlib import Path
from types import SimpleNamespace

from romm_vita_manager import archive_utils


def test_7z_listing_skips_archive_metadata_and_keeps_final_member(monkeypatch, tmp_path: Path) -> None:
    archive = tmp_path / "RetroArch_data.7z"
    archive.write_bytes(b"not-used-by-parser-test")
    listing = """Listing archive: RetroArch_data.7z

--
Path = RetroArch_data.7z
Type = 7z
Physical Size = 123

----------
Path = retroarch/assets
Size = 0
Folder = +

Path = retroarch/assets/menu.png
Size = 42
Folder = -"""

    monkeypatch.setattr(archive_utils.shutil, "which", lambda _name: "/usr/bin/7z")
    monkeypatch.setattr(
        archive_utils.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=listing, stderr=""),
    )

    entries = archive_utils.list_archive(archive)

    assert [entry.name for entry in entries] == [
        "retroarch/assets",
        "retroarch/assets/menu.png",
    ]
    assert entries[0].is_directory is True
    assert entries[0].size == 0
    assert entries[1].is_directory is False
    assert entries[1].size == 42
