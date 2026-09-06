from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from romm_vita_manager import config as config_module
from romm_vita_manager.three_ds_storage import (
    ThreeDSMountedStorageBackend,
    configured_3ds_storage_root,
    with_3ds_storage_root,
)


def _make_3ds_root(tmp_path: Path) -> Path:
    root = tmp_path / "3ds-card"
    root.mkdir()
    (root / "boot.firm").write_bytes(b"firm")
    (root / "luma").mkdir()
    return root


def test_configured_root_requires_valid_3ds_markers(tmp_path: Path):
    root = _make_3ds_root(tmp_path)
    config = {"devices": {"3ds": {"storage_root": str(root)}}}

    assert configured_3ds_storage_root(config) == root.resolve()

    invalid = tmp_path / "ordinary-folder"
    invalid.mkdir()
    assert configured_3ds_storage_root(
        {"devices": {"3ds": {"storage_root": str(invalid)}}}
    ) is None


def test_with_storage_root_preserves_ftp_settings(tmp_path: Path):
    root = _make_3ds_root(tmp_path)
    original = {
        "devices": {
            "3ds": {
                "host": "192.0.2.10",
                "port": 5000,
                "username": "anonymous",
            }
        }
    }

    updated = with_3ds_storage_root(original, root)

    assert updated["devices"]["3ds"]["host"] == "192.0.2.10"
    assert updated["devices"]["3ds"]["port"] == 5000
    assert updated["devices"]["3ds"]["storage_root"] == str(root.resolve())
    assert "storage_root" not in original["devices"]["3ds"]


def test_with_storage_root_rejects_unrecognised_directory(tmp_path: Path):
    root = tmp_path / "ordinary-folder"
    root.mkdir()

    with pytest.raises(ValueError, match="3DS SD-card markers"):
        with_3ds_storage_root({}, root)


def test_backend_confines_destination_to_card_root(tmp_path: Path):
    root = _make_3ds_root(tmp_path)
    backend = ThreeDSMountedStorageBackend(root)

    with pytest.raises(ValueError):
        backend.destination_path("../escape.bin")


def test_backend_copy_skip_and_safe_replacement(tmp_path: Path):
    root = _make_3ds_root(tmp_path)
    backend = ThreeDSMountedStorageBackend(root)
    source = tmp_path / "game.gba"
    source.write_bytes(b"first-version")

    result, target = backend.upload(source, "/roms/gba/game.gba")
    assert result == "copied"
    assert target.read_bytes() == b"first-version"

    result, _ = backend.upload(source, "/roms/gba/game.gba")
    assert result == "skipped"
    assert target.read_bytes() == b"first-version"

    source.write_bytes(b"replacement-is-longer")
    result, _ = backend.upload(source, "/roms/gba/game.gba")
    assert result == "different"
    assert target.read_bytes() == b"first-version"

    result, _ = backend.upload(source, "/roms/gba/game.gba", overwrite=True)
    assert result == "copied"
    assert target.read_bytes() == b"replacement-is-longer"


def test_backend_cancel_preserves_existing_destination(tmp_path: Path):
    root = _make_3ds_root(tmp_path)
    backend = ThreeDSMountedStorageBackend(root)
    target = root / "roms" / "gba" / "game.gba"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"existing")
    source = tmp_path / "game.gba"
    source.write_bytes(b"new-and-different")
    cancelled = threading.Event()
    cancelled.set()

    result, _ = backend.upload(
        source,
        "/roms/gba/game.gba",
        overwrite=True,
        cancel_event=cancelled,
    )

    assert result == "cancelled"
    assert target.read_bytes() == b"existing"
    assert not list(target.parent.glob("*.part"))


def test_backend_rejects_insufficient_free_space(monkeypatch, tmp_path: Path):
    root = _make_3ds_root(tmp_path)
    backend = ThreeDSMountedStorageBackend(root)
    source = tmp_path / "large.gba"
    source.write_bytes(b"1234567890")
    monkeypatch.setattr(
        "romm_vita_manager.three_ds_storage.storage_summary",
        lambda _root: (100, 1),
    )

    with pytest.raises(OSError, match="Not enough free space"):
        backend.upload(source, "/roms/gba/large.gba")

    assert not (root / "roms" / "gba" / "large.gba").exists()


def test_ftp_only_config_save_preserves_mounted_storage_root(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config_module, "APP_DIR", tmp_path)
    existing_root = tmp_path / "3ds-card"
    config_path.write_text(
        json.dumps(
            {
                "devices": {
                    "3ds": {
                        "host": "192.0.2.1",
                        "port": 5000,
                        "storage_root": str(existing_root),
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    config_module.save_config(
        {
            "devices": {
                "3ds": {
                    "host": "192.0.2.2",
                    "port": 5001,
                }
            }
        }
    )
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["devices"]["3ds"]["storage_root"] == str(existing_root)
    assert saved["devices"]["3ds"]["host"] == "192.0.2.2"

    config_module.save_config(
        {
            "devices": {
                "3ds": {
                    "host": "192.0.2.2",
                    "port": 5001,
                    "storage_root": "",
                }
            }
        }
    )
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["devices"]["3ds"]["storage_root"] == ""
