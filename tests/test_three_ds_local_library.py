from pathlib import Path

from romm_vita_manager.romm import scan_games


LIBRARY_PATH = Path(__file__).parents[1] / "romm_vita_manager" / "three_ds_library.py"


def test_local_library_source_contract_stays_headless():
    source = LIBRARY_PATH.read_text(encoding="utf-8")

    assert "from .models import Game" in source
    assert "from .library_sources import get_library_source" in source
    assert 'PACKAGE_GENERATION_TARGETS = frozenset({"native_gba", "vc_cia"})' in source
    assert "if target.key not in PACKAGE_GENERATION_TARGETS" in source
    assert 'game.path.suffix.casefold() != ".cia"' in source
    assert 'if self._source_mode() == "local":' in source
    assert "self._load_local_library()" in source
    assert "scan_games(root)" in source


def test_local_platform_labels_are_normalized_before_target_selection():
    source = LIBRARY_PATH.read_text(encoding="utf-8")

    assert "def _local_platform_slug(value: str) -> str:" in source
    assert "if folded in PLATFORM_LABELS:" in source
    assert "for slug, label in PLATFORM_LABELS.items():" in source
    assert "if label.casefold() == folded:" in source


def test_local_scan_recognizes_dedicated_and_retroarch_formats(tmp_path: Path):
    expected = {
        "virtualboy": "Wario.vb",
        "wonderswan": "Gunpey.ws",
        "neo-geo-pocket": "Sonic.ngp",
        "vectrex": "Minestorm.vec",
        "c64": "Game.d64",
        "amiga": "Game.adf",
    }
    for platform, filename in expected.items():
        path = tmp_path / platform / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"rom")

    games = scan_games(tmp_path)
    found = {(game.source_platform, game.path.name) for game in games}
    assert found == set(expected.items())


def test_main_3ds_library_reuses_verified_transfer_worker():
    source = LIBRARY_PATH.read_text(encoding="utf-8")

    assert "ThreeDSTransferWorker" in source
    assert "worker = ThreeDSTransferWorker(" in source
    assert "worker.cancel()" in source
    assert "overwrite=overwrite" in source
    assert "Open Device → Connection setup" in source
