from pathlib import Path

from romm_vita_manager.mappings import normalize_platform_slug
from romm_vita_manager.romm import scan_games


ROOT = Path(__file__).parents[1]
LIBRARY_PATH = ROOT / "romm_vita_manager" / "three_ds_library.py"
DEPLOY_PATH = ROOT / "romm_vita_manager" / "three_ds_filesystem_deploy.py"


def test_local_library_source_contract_stays_headless():
    source = LIBRARY_PATH.read_text(encoding="utf-8")

    assert "from .models import Game" in source
    assert "from .library_sources import get_library_source" in source
    assert 'PACKAGE_GENERATION_TARGETS = frozenset({"native_gba", "vc_cia"})' in source
    assert "if target.key not in PACKAGE_GENERATION_TARGETS" in source
    assert "available_targets_for_file" in source
    assert "available_targets_for_file(_platform_slug(game), _filename(game))" in source
    assert 'if self._source_mode() == "local":' in source
    assert "self._load_local_library()" in source
    assert "scan_games(root)" in source


def test_local_platform_labels_are_normalized_before_target_selection():
    assert normalize_platform_slug("gba") == "gba"
    assert normalize_platform_slug("Game Boy Advance") == "gba"
    assert normalize_platform_slug("Nintendo 64") == "n64"

    source = LIBRARY_PATH.read_text(encoding="utf-8")
    assert "return normalize_platform_slug(game.source_platform)" in source


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


def test_main_3ds_library_delegates_transport_after_target_selection():
    source = LIBRARY_PATH.read_text(encoding="utf-8")

    assert "from .three_ds_filesystem_deploy import ThreeDSFilesystemDeployDialog" in source
    assert "ThreeDSFilesystemDeployDialog(self.config, game, target_key, self).exec()" in source
    assert "self.open_manager_callback(game, target_key)" in source
    assert "ThreeDSTransferWorker" not in source


def test_filesystem_dialog_uses_one_payload_aware_worker_for_local_or_romm_games():
    source = DEPLOY_PATH.read_text(encoding="utf-8")

    assert "from .models import Game" in source
    assert "from .three_ds_filesystem_worker import ThreeDSFilesystemTransferWorker" in source
    assert "ThreeDSMountedTransferWorker" not in source
    assert "ThreeDSTransferWorker" not in source
    assert "if isinstance(self.game, RomMRemoteGame):" in source
    assert "return self.game.path, None, \"\", \"\"" in source
    assert "worker = ThreeDSFilesystemTransferWorker(" in source
    assert "target_key=self.target_key" in source
    assert "platform_slug=self.platform_slug" in source
    assert "worker.destination_resolved.connect(self._destination_resolved)" in source
    assert "self._closing_requested = True" in source
    assert "QTimer.singleShot(0, self.close)" in source
