from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from romm_vita_manager.fbi_remote_install import FBIUrlServer


def _server_state() -> FBIUrlServer:
    server = object.__new__(FBIUrlServer)
    server.file_path = Path("test.cia")
    server.request_started_event = threading.Event()
    server.served_event = threading.Event()
    server.request_failed_event = threading.Event()
    server.ack_event = threading.Event()
    server.control_closed_event = threading.Event()
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


def test_wait_for_request_start_treats_pre_download_ack_as_declined() -> None:
    server = _server_state()
    server.ack_event.set()

    with pytest.raises(PermissionError, match="declined or FBI rejected"):
        server.wait_for_request_start(timeout=1)


def test_interrupted_http_transfer_is_reported() -> None:
    server = _server_state()
    server.request_started_event.set()
    server.request_failed_event.set()

    with pytest.raises(ConnectionError, match="HTTP transfer ended"):
        server.wait_for_download(timeout=1)


def test_http_delivery_is_not_complete_until_fbi_acknowledges_install() -> None:
    server = _server_state()
    server.request_started_event.set()
    server.served_event.set()

    with pytest.raises(TimeoutError, match="did not report that the installation finished"):
        server.wait_for_download(timeout=0)

    server.ack_event.set()
    server.wait_for_download(timeout=1)


def test_closed_control_socket_after_http_send_is_reported() -> None:
    server = _server_state()
    server.request_started_event.set()
    server.served_event.set()
    server.control_closed_event.set()

    with pytest.raises(ConnectionError, match="without reporting install completion"):
        server.wait_for_download(timeout=1)


def test_wait_for_download_observes_cancellation() -> None:
    server = _server_state()
    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(InterruptedError):
        server.wait_for_download(timeout=1, cancel_event=cancel_event)
