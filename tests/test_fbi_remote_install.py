from types import SimpleNamespace
import threading

import pytest

from romm_vita_manager.fbi_remote_install import FBIUrlServer


def _server_state() -> FBIUrlServer:
    server = object.__new__(FBIUrlServer)
    server.request_started_event = threading.Event()
    server.served_event = threading.Event()
    server.request_failed_event = threading.Event()
    server.request_path = None
    server._request_lock = threading.Lock()
    server.httpd = SimpleNamespace(server_address=("0.0.0.0", 8080))
    return server


def test_request_is_complete_only_after_successful_http_send() -> None:
    server = _server_state()
    server.request_started()
    server.request_finished(False)
    assert server.request_started_event.is_set()
    assert server.request_failed_event.is_set()
    assert not server.served_event.is_set()

    server.request_finished(True)
    assert server.served_event.is_set()
    assert not server.request_failed_event.is_set()


def test_interrupted_http_transfer_is_reported() -> None:
    server = _server_state()
    server.request_started_event.set()
    server.request_failed_event.set()

    with pytest.raises(ConnectionError, match="HTTP transfer ended"):
        server.wait_for_download(timeout=1)


def test_wait_for_download_observes_cancellation() -> None:
    server = _server_state()
    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(InterruptedError):
        server.wait_for_download(timeout=1, cancel_event=cancel_event)
