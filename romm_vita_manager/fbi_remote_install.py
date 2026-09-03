from __future__ import annotations

import errno
import socket
import struct
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote


class _Handler(SimpleHTTPRequestHandler):
    served_event: threading.Event
    directory_path: str

    def __init__(self, *args, directory: str, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        try:
            return super().do_GET()
        finally:
            self.served_event.set()


class FBIUrlServer:
    """Temporary HTTP server plus FBI Remote Install URL sender."""

    def __init__(self, file_path: Path, *, bind_host: str = "0.0.0.0", port: int = 8080):
        self.file_path = file_path.expanduser().resolve()
        if not self.file_path.is_file():
            raise FileNotFoundError(f"CIA file does not exist: {self.file_path}")
        self.bind_host = bind_host
        self.requested_port = port
        self.served_event = threading.Event()
        self._fbi_socket: socket.socket | None = None
        self._ack_thread: threading.Thread | None = None

        server = self

        class FBIHandler(_Handler):
            served_event = server.served_event

            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(server.file_path.parent), **kwargs)

        try:
            self.httpd = ThreadingHTTPServer((bind_host, port), FBIHandler)
        except OSError as exc:
            if port != 0 and exc.errno == errno.EADDRINUSE:
                # Prefer the conventional FBI servefiles.py port, but never let a
                # stale process or another local service prevent a deployment.
                self.httpd = ThreadingHTTPServer((bind_host, 0), FBIHandler)
            else:
                raise
        self.httpd.daemon_threads = True
        self.http_thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1])

    def start(self) -> None:
        self.http_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.http_thread.start()

    def local_address(self, preferred_host: str | None = None, peer_host: str | None = None) -> str:
        if preferred_host:
            return preferred_host.strip()

        if peer_host:
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # UDP connect does not send a packet. It asks the OS which local
                # interface/address it would use to reach the 3DS specifically.
                probe.connect((peer_host.strip(), 5000))
                return str(probe.getsockname()[0])
            except OSError:
                pass
            finally:
                probe.close()

        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 53))
            return str(probe.getsockname()[0])
        except OSError:
            return "127.0.0.1"
        finally:
            probe.close()

    def url_for(self, host: str) -> str:
        return f"http://{host}:{self.port}/{quote(self.file_path.name)}"

    def send_to_fbi(self, three_ds_ip: str, host: str | None = None, timeout: float = 8.0) -> str:
        """Send the FBI URL and return once FBI has accepted the URL payload.

        FBI sends its one-byte acknowledgement only after the install action closes
        the connection, which can be much later than the initial URL hand-off.
        Waiting for that ACK here makes the UI falsely report a timeout while FBI is
        already displaying the installation prompt.
        """
        three_ds_ip = three_ds_ip.strip()
        if not three_ds_ip:
            raise ValueError("3DS IP address is required for FBI Remote Install.")
        if self._fbi_socket is not None:
            raise RuntimeError("An FBI Remote Install request is already active.")

        url = self.url_for(self.local_address(host, three_ds_ip))
        payload = url.encode("ascii")
        packet = struct.pack("!L", len(payload)) + payload
        sock = socket.create_connection((three_ds_ip, 5000), timeout=timeout)
        try:
            sock.sendall(packet)
        except Exception:
            sock.close()
            raise

        self._fbi_socket = sock
        self._ack_thread = threading.Thread(target=self._wait_for_ack, daemon=True)
        self._ack_thread.start()
        return url

    def _wait_for_ack(self) -> None:
        sock = self._fbi_socket
        if sock is None:
            return
        try:
            sock.settimeout(None)
            sock.recv(1)
        except OSError:
            pass

    def wait_for_download(self, timeout: float = 120.0) -> None:
        if not self.served_event.wait(timeout):
            raise TimeoutError(
                "FBI accepted the URL but the 3DS could not download the CIA from this PC. "
                "Check the PC firewall and that the detected PC address is on the same LAN."
            )

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        if self.http_thread is not None:
            self.http_thread.join(timeout=2)
            self.http_thread = None
        if self._fbi_socket is not None:
            try:
                self._fbi_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._fbi_socket.close()
            except OSError:
                pass
            self._fbi_socket = None
        self._ack_thread = None

    def __enter__(self) -> "FBIUrlServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
