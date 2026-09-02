from pathlib import Path

from romm_vita_manager.storage_validation import validate_storage


def test_validate_3ds_storage(tmp_path: Path):
    for name in ("boot.firm", "boot.3dsx"):
        (tmp_path / name).write_bytes(b"")
    (tmp_path / "luma").mkdir()
    (tmp_path / "gm9").mkdir()
    (tmp_path / "3ds").mkdir()

    result = validate_storage(tmp_path)

    assert result.kind == "3ds-sd"
    assert result.confidence == "high"
    assert "boot.firm" in result.signatures
    assert "luma/" in result.signatures


def test_validate_twilight_storage(tmp_path: Path):
    (tmp_path / "_nds").mkdir()
    (tmp_path / "BOOT.NDS").write_bytes(b"")
    (tmp_path / "roms").mkdir()

    result = validate_storage(tmp_path)

    assert result.kind == "ds-storage"
    assert result.confidence == "high"


def test_validate_r4_storage(tmp_path: Path):
    (tmp_path / "__rpg").mkdir()

    result = validate_storage(tmp_path)

    assert result.kind == "ds-flashcard"
    assert result.confidence == "medium"
    assert "__rpg/" in result.signatures


def test_validate_unknown_storage(tmp_path: Path):
    (tmp_path / "roms").mkdir()

    result = validate_storage(tmp_path)

    assert result.kind == "unknown"
    assert result.confidence == "low"
    assert "roms/" in result.signatures
