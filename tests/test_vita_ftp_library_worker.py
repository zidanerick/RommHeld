from __future__ import annotations

from pathlib import Path

from romm_vita_manager.models import Game
from romm_vita_manager.vita_ftp import VitaFtpSettings
from romm_vita_manager.vita_ftp_library import VitaFtpCopyWorker


def make_game(path: Path, *, name: str, platform: str = "snes") -> Game:
    return Game(
        path=path,
        name=name,
        source_platform=platform,
        size=path.stat().st_size,
        relative=Path(path.name),
    )


def test_vita_ftp_copy_worker_reports_copied_and_skipped(monkeypatch, tmp_path: Path):
    first_path = tmp_path / "first.sfc"
    second_path = tmp_path / "second.sfc"
    first_path.write_bytes(b"first")
    second_path.write_bytes(b"second")
    first = make_game(first_path, name="First")
    second = make_game(second_path, name="Second")
    calls: list[tuple[str, str]] = []

    class FakeBackend:
        def __init__(self, settings):
            self.settings = settings

        def connect(self):
            calls.append(("connect", self.settings.host))

        def upload(self, local_path, destination, **kwargs):
            calls.append((local_path.name, destination))
            if local_path == first.path:
                return "copied", first.size
            return "skipped", second.size

        def close(self):
            calls.append(("close", ""))

    monkeypatch.setattr("romm_vita_manager.vita_ftp_library.VitaFtpBackend", FakeBackend)
    worker = VitaFtpCopyWorker(
        VitaFtpSettings(host="192.0.2.20"),
        [
            (first, "ux0:/data/first.sfc", "First target"),
            (second, "ux0:/data/second.sfc", "Second target"),
        ],
    )
    finished: list[tuple[int, int, int]] = []
    failures: list[str] = []
    progress: list[tuple[int, str, str]] = []
    worker.finished_ok.connect(lambda copied, skipped, cancelled: finished.append((copied, skipped, cancelled)))
    worker.failed.connect(failures.append)
    worker.progress.connect(lambda percent, name, detail: progress.append((percent, name, detail)))

    worker.run()

    assert finished == [(1, 1, 0)]
    assert failures == []
    assert calls[0] == ("connect", "192.0.2.20")
    assert calls[-1] == ("close", "")
    assert ("first.sfc", "ux0:/data/first.sfc") in calls
    assert ("second.sfc", "ux0:/data/second.sfc") in calls
    assert any(name == "First" and detail == "Copied and verified" for _percent, name, detail in progress)
    assert any(name == "Second" and detail == "Already present" for _percent, name, detail in progress)


def test_vita_ftp_copy_worker_cancellation_stops_batch_and_closes_backend(monkeypatch, tmp_path: Path):
    first_path = tmp_path / "first.sfc"
    second_path = tmp_path / "second.sfc"
    first_path.write_bytes(b"first")
    second_path.write_bytes(b"second")
    first = make_game(first_path, name="First")
    second = make_game(second_path, name="Second")
    calls: list[str] = []

    class FakeBackend:
        def __init__(self, settings):
            self.settings = settings

        def connect(self):
            calls.append("connect")

        def upload(self, local_path, destination, **kwargs):
            calls.append(local_path.name)
            kwargs["progress"](1)
            kwargs["cancel_event"].set()
            return "cancelled", 1

        def close(self):
            calls.append("close")

    monkeypatch.setattr("romm_vita_manager.vita_ftp_library.VitaFtpBackend", FakeBackend)
    worker = VitaFtpCopyWorker(
        VitaFtpSettings(host="192.0.2.20"),
        [
            (first, "ux0:/data/first.sfc", "First target"),
            (second, "ux0:/data/second.sfc", "Second target"),
        ],
    )
    finished: list[tuple[int, int, int]] = []
    failures: list[str] = []
    worker.finished_ok.connect(lambda copied, skipped, cancelled: finished.append((copied, skipped, cancelled)))
    worker.failed.connect(failures.append)

    worker.run()

    assert finished == [(0, 0, 1)]
    assert failures == []
    assert calls == ["connect", "first.sfc", "close"]


def test_vita_ftp_copy_worker_failure_closes_backend(monkeypatch, tmp_path: Path):
    first_path = tmp_path / "first.sfc"
    second_path = tmp_path / "second.sfc"
    first_path.write_bytes(b"first")
    second_path.write_bytes(b"second")
    first = make_game(first_path, name="First")
    second = make_game(second_path, name="Second")
    calls: list[str] = []

    class FakeBackend:
        def __init__(self, settings):
            self.settings = settings

        def connect(self):
            calls.append("connect")

        def upload(self, local_path, destination, **kwargs):
            calls.append(local_path.name)
            if local_path == second.path:
                raise OSError("wireless link lost")
            return "copied", local_path.stat().st_size

        def close(self):
            calls.append("close")

    monkeypatch.setattr("romm_vita_manager.vita_ftp_library.VitaFtpBackend", FakeBackend)
    worker = VitaFtpCopyWorker(
        VitaFtpSettings(host="192.0.2.20"),
        [
            (first, "ux0:/data/first.sfc", "First target"),
            (second, "ux0:/data/second.sfc", "Second target"),
        ],
    )
    finished: list[tuple[int, int, int]] = []
    failures: list[str] = []
    worker.finished_ok.connect(lambda copied, skipped, cancelled: finished.append((copied, skipped, cancelled)))
    worker.failed.connect(failures.append)

    worker.run()

    assert finished == []
    assert failures == ["wireless link lost"]
    assert calls == ["connect", "first.sfc", "second.sfc", "close"]


def test_vita_ftp_copy_worker_validates_all_sources_before_connect(monkeypatch, tmp_path: Path):
    source_path = tmp_path / "game.sfc"
    source_path.write_bytes(b"source")
    game = make_game(source_path, name="Game")
    game = Game(
        path=game.path,
        name=game.name,
        source_platform=game.source_platform,
        size=game.size + 1,
        relative=game.relative,
    )
    connected: list[bool] = []

    class FakeBackend:
        def __init__(self, settings):
            self.settings = settings

        def connect(self):
            connected.append(True)

        def close(self):
            pass

    monkeypatch.setattr("romm_vita_manager.vita_ftp_library.VitaFtpBackend", FakeBackend)
    worker = VitaFtpCopyWorker(
        VitaFtpSettings(host="192.0.2.20"),
        [(game, "ux0:/data/game.sfc", "Target")],
    )
    failures: list[str] = []
    worker.failed.connect(failures.append)

    worker.run()

    assert connected == []
    assert len(failures) == 1
    assert "Source changed since the library scan" in failures[0]
