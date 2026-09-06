from __future__ import annotations

import ast
from pathlib import Path

from romm_vita_manager.three_ds_paths import default_3ds_destination


MANAGER_PATH = Path(__file__).parents[1] / "romm_vita_manager" / "three_ds_manager.py"


def test_default_3ds_destination_for_nds():
    assert default_3ds_destination("Mario.nds", ".nds") == "/roms/nds/Mario.nds"


def test_default_3ds_destination_for_gba():
    assert default_3ds_destination("Metroid.gba", ".gba") == "/roms/gba/Metroid.gba"


def test_default_3ds_destination_leaves_other_formats_explicit():
    assert default_3ds_destination("Homebrew.3dsx", ".3dsx") == "Homebrew.3dsx"
    assert default_3ds_destination("Title.cia", ".cia") == "Title.cia"


def test_manager_uses_shared_runtime_preference_policy_without_importing_qt():
    source = MANAGER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "get_device_preference" in imported_names
    assert "preferred_target_key" in imported_names
    assert "get_device_preference" in called_names
    assert "preferred_target_key" in called_names
    assert '"native_gba" if game.platform_slug == "gba" else "retroarch"' not in source


def test_manager_uses_file_aware_targets_for_local_and_romm_records():
    source = MANAGER_PATH.read_text(encoding="utf-8")

    assert "available_targets_for_file" in source
    assert "normalize_platform_slug" in source
    assert "targets = available_targets_for_file(_platform_slug(game), _filename(game))" in source
    assert 'PACKAGE_GENERATION_TARGETS = frozenset({"native_gba", "vc_cia"})' in source
    assert "if target.key not in PACKAGE_GENERATION_TARGETS" in source
    assert "games = [game for game in scan_games(root) if _targets_for_game(game)]" in source


def test_manager_disables_deployment_without_a_safe_target():
    source = MANAGER_PATH.read_text(encoding="utf-8")

    assert "has_target = self.target_combo.count() > 0" in source
    assert "and has_target" in source
    assert 'target_key = str(self.target_combo.currentData() or "")' in source
    assert 'target_key = str(self.target_combo.currentData() or "retroarch")' not in source
    assert "No safe deployment route is available for this file format" in source
    assert "This file format does not have a supported Nintendo 3DS deployment route" in source


def test_manager_ftp_save_preserves_independently_owned_3ds_fields_in_memory():
    source = MANAGER_PATH.read_text(encoding="utf-8")

    assert 'device = dict(devices.get("3ds", {}))' in source
    assert 'device.update(' in source
    assert 'devices["3ds"] = device' in source
    assert 'devices["3ds"] = {' not in source


def test_manager_routes_all_implemented_romm_vc_families_to_package_dialogs():
    source = MANAGER_PATH.read_text(encoding="utf-8")

    assert 'if target_key == "native_gba":' in source
    assert 'if target_key == "vc_cia":' in source
    assert 'if platform == "gba":' in source
    assert 'if platform in {"gb", "gbc", "nes", "gamegear", "snes"}:' in source
    assert "from .gba_vc_deploy import GbaVcDeployDialog" in source
    assert "from .classic_vc_deploy import ClassicVcDeployDialog" in source
    assert "ClassicVcDeployDialog(self.config, selected, self).exec()" in source
    assert "available for RomM-backed GBA, GB, GBC, NES, Game Gear, and supported SNES titles" in source


def test_manager_preflights_remote_destination_before_romm_download():
    source = MANAGER_PATH.read_text(encoding="utf-8")

    remote_size = source.index("remote_size = self.backend.remote_size(self.destination)")
    resolve_remote_source = source.index("source = self._resolve_source()", remote_size)
    assert remote_size < resolve_remote_source
    assert 'self.completed.emit("skipped")' in source
    assert 'self.completed.emit("different")' in source


def test_manager_downloads_first_when_romm_size_is_unknown():
    source = MANAGER_PATH.read_text(encoding="utf-8")

    unknown_size = source.index("if expected_size <= 0:")
    resolve_source = source.index("source = self._resolve_source()", unknown_size)
    actual_size = source.index("expected_size = source.stat().st_size", resolve_source)
    remote_size = source.index("remote_size = self.backend.remote_size(self.destination)")
    assert unknown_size < resolve_source < actual_size < remote_size


def test_manager_requires_explicit_safe_replacement():
    source = MANAGER_PATH.read_text(encoding="utf-8")

    assert "overwrite=self.overwrite" in source
    assert "Replace existing 3DS file?" in source
    assert "separate staging file" in source
    assert "keep the existing destination until the replacement is ready" in source
    assert "self.send_selected(overwrite=True)" in source


def test_manager_locks_selection_during_transfer():
    source = MANAGER_PATH.read_text(encoding="utf-8")

    assert "self.game_list.setEnabled(not ftp_busy and not library_busy)" in source


def test_manager_propagates_cancel_to_romm_download_and_handles_interrupt_cleanly():
    source = MANAGER_PATH.read_text(encoding="utf-8")

    assert "cancel_event=self.cancel_event" in source
    assert "progress=lambda done, _total: self.progress.emit(done)" in source
    assert "except InterruptedError:" in source
    assert 'self.completed.emit("cancelled")' in source


def test_manager_close_detaches_background_workers_instead_of_waiting():
    source = MANAGER_PATH.read_text(encoding="utf-8")

    assert "_DETACHED_WORKERS" in source
    assert "def _keep_worker_alive" in source
    assert "def _request_background_shutdown" in source
    assert "def reject(self)" in source
    close_event = source.split("def closeEvent(self, event) -> None:", 1)[1]
    assert "event.ignore()" not in close_event
    assert "self.setEnabled(False)" not in close_event
    assert "self._request_background_shutdown()" in close_event
    assert "super().closeEvent(event)" in close_event
