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
    assert result.confidence == "medium"


def test_validate_current_nds_bootstrap_layout(tmp_path: Path):
    (tmp_path / "_nds" / "TWiLightMenu").mkdir(parents=True)
    (tmp_path / "_nds" / "nds-bootstrap-release.nds").write_bytes(b"nds")
    (tmp_path / "_nds" / "nds-bootstrap-release.ver").write_text("v2.16.0", encoding="utf-8")
    (tmp_path / "BOOT.NDS").write_bytes(b"boot")
    (tmp_path / "roms" / "nds" / "saves").mkdir(parents=True)

    result = validate_storage(tmp_path)

    assert result.kind == "ds-storage"
    assert result.confidence == "high"
    assert "_nds/nds-bootstrap*.nds" in result.signatures
    assert "_nds/nds-bootstrap*.ver" in result.signatures


def test_validate_r4_storage(tmp_path: Path):
    (tmp_path / "__rpg").mkdir()

    result = validate_storage(tmp_path)

    assert result.kind == "ds-flashcard"
    assert result.confidence == "medium"
    assert "__rpg/" in result.signatures


def test_validate_boot_alt_as_flashcard_storage(tmp_path: Path):
    (tmp_path / "BOOT_ALT.NDS").write_bytes(b"boot")

    result = validate_storage(tmp_path)

    assert result.kind == "ds-flashcard"
    assert "BOOT_ALT.NDS" in result.signatures


def test_validate_3ds_twl_storage_is_not_misclassified_as_ds(tmp_path: Path):
    (tmp_path / "Nintendo 3DS").mkdir()
    (tmp_path / "_nds").mkdir()
    (tmp_path / "roms").mkdir()

    result = validate_storage(tmp_path)

    assert result.kind == "3ds-sd"


def test_validate_unknown_storage(tmp_path: Path):
    (tmp_path / "roms").mkdir()

    result = validate_storage(tmp_path)

    assert result.kind == "unknown"
    assert result.confidence == "low"
    assert "roms/" in result.signatures
