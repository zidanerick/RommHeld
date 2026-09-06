from pathlib import Path

import romm_vita_manager.three_ds_title_inventory as inventory


_ID0 = "0" * 32
_ID1 = "1" * 32


def _title_dir(root: Path, title_id: str, *, id0: str = _ID0, id1: str = _ID1) -> Path:
    high, low = title_id[:8], title_id[8:]
    path = root / "Nintendo 3DS" / id0 / id1 / "title" / high / low
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_mounted_sd_title_ids_reads_visible_title_directory_names(tmp_path: Path):
    _title_dir(tmp_path, "0004000000F12300")
    _title_dir(tmp_path, "000400000E123400")
    _title_dir(tmp_path, "0004008C00123400")

    found = inventory.mounted_sd_title_ids(tmp_path)

    assert bytes.fromhex("0004000000F12300") in found
    assert bytes.fromhex("000400000E123400") in found
    assert bytes.fromhex("0004008C00123400") in found


def test_mounted_sd_title_ids_scans_multiple_console_directories(tmp_path: Path):
    _title_dir(tmp_path, "0004000000F10000", id0="A" * 32, id1="B" * 32)
    _title_dir(tmp_path, "0004000000F10100", id0="C" * 32, id1="D" * 32)

    assert inventory.mounted_sd_title_ids(tmp_path) == frozenset(
        {
            bytes.fromhex("0004000000F10000"),
            bytes.fromhex("0004000000F10100"),
        }
    )


def test_mounted_sd_title_ids_ignores_malformed_directory_components(tmp_path: Path):
    _title_dir(tmp_path, "0004000000F12300")

    bad_id0 = tmp_path / "Nintendo 3DS" / "not-an-id0" / _ID1 / "title" / "00040000" / "00F99900"
    bad_id0.mkdir(parents=True)
    bad_high = tmp_path / "Nintendo 3DS" / _ID0 / _ID1 / "title" / "nothex!!" / "00F99800"
    bad_high.mkdir(parents=True)

    assert inventory.mounted_sd_title_ids(tmp_path) == frozenset(
        {bytes.fromhex("0004000000F12300")}
    )


def test_mounted_sd_title_ids_returns_empty_without_3ds_tree(tmp_path: Path):
    assert inventory.mounted_sd_title_ids(tmp_path) == frozenset()


def test_configured_inventory_uses_only_validated_configured_root(tmp_path: Path, monkeypatch):
    _title_dir(tmp_path, "0004000000F12300")
    monkeypatch.setattr(inventory, "configured_3ds_storage_root", lambda config: tmp_path)

    found = inventory.configured_mounted_sd_title_ids({"devices": {"3ds": {}}})

    assert found == frozenset({bytes.fromhex("0004000000F12300")})


def test_configured_inventory_is_empty_without_validated_root(monkeypatch):
    monkeypatch.setattr(inventory, "configured_3ds_storage_root", lambda config: None)
    assert inventory.configured_mounted_sd_title_ids({}) == frozenset()
