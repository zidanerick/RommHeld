from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "romm_vita_manager" / "vita_setup.py").read_text(encoding="utf-8")


def test_vita_setup_offers_usb_and_ftp_transports():
    assert 'self.transport_combo.addItem("VitaShell USB · Recommended", "usb")' in SOURCE
    assert 'self.transport_combo.addItem("VitaShell FTP · Wireless / PlayStation TV", "ftp")' in SOURCE
    assert "Device → Send file / configure FTP" in SOURCE


def test_vita_setup_routes_ftp_staging_through_transport_adapter():
    assert "from .vita_package_transport import stage_package_via_ftp" in SOURCE
    assert "result, target = stage_package_via_ftp(" in SOURCE
    assert 'if self.transport == "ftp":' in SOURCE


def test_vita_setup_does_not_start_stage_worker_until_download_thread_finishes():
    finished_handler = SOURCE.index("def _worker_finished(self) -> None:")
    prompt = SOURCE.index('"Download complete"', finished_handler)
    start_stage = SOURCE.index('self._start_worker(package.key, "stage")', prompt)
    package_finished = SOURCE.index("def _package_finished(self, action: str, path: str) -> None:")

    assert finished_handler < prompt < start_stage < package_finished
    assert "self._pending_stage_key = package.key" in SOURCE
    assert "self.worker = None" in SOURCE[finished_handler:package_finished]
