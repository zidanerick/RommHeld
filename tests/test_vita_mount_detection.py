from pathlib import Path

from romm_vita_manager.vita import find_vita_mounts, is_vita_mount


def _mkdirs(root: Path, *relative_paths: str) -> None:
    for relative in relative_paths:
        (root / relative).mkdir(parents=True, exist_ok=True)


def test_vitashell_ux0_structure_is_detected(tmp_path: Path):
    _mkdirs(tmp_path, "app/VITASHELL", "VitaShell", "data")

    assert is_vita_mount(tmp_path)


def test_generic_vita_like_folders_without_vitashell_are_rejected(tmp_path: Path):
    _mkdirs(tmp_path, "app", "appmeta", "data", "pspemu", "tai")

    assert not is_vita_mount(tmp_path)


def test_vitashell_markers_still_need_supporting_ux0_structure(tmp_path: Path):
    _mkdirs(tmp_path, "app/VITASHELL", "VitaShell")

    assert not is_vita_mount(tmp_path)


def test_find_vita_mounts_filters_candidates(monkeypatch, tmp_path: Path):
    vita = tmp_path / "vita"
    other = tmp_path / "other"
    _mkdirs(vita, "app/VITASHELL", "VitaShell", "data")
    _mkdirs(other, "app", "data", "tai")
    monkeypatch.setattr(
        "romm_vita_manager.vita.writable_volumes",
        lambda: [other, vita],
    )

    assert find_vita_mounts() == [vita]
