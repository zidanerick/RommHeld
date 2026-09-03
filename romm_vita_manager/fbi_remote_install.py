from __future__ import annotations

import errno
import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote


class _Handler(BaseHTTPRequestHandler):
    server: "_HttpServer"

    def log_message(self, format: str, *args) -> None:
        return

    def _serve_file(self, *, mark_download_complete: bool) -> None:
        source = self.server.owner.file_path
        try:
            size = source.stat().st_size
        except OSError as exc:
            self.send_error(404, str(exc))
            return

        if mark_download_complete:
            self.server.owner.request_started()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(size))
            self.end_headers()
            if self.command == "HEAD":
                return
            with source.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        finally:
            if mark_download_complete:
                self.server.owner.request_finished()

    def _requested_name(self) -> str:
        return self.path.split("?", 1)[0].lstrip("/")

    def do_GET(self) -> None:
        if self._requested_name() == self.server.owner.file_path.name:
            try:
                self._serve_file(mark_download_complete=True)
            except (BrokenPipeError, ConnectionResetError):
                self.server.owner.request_finished()
            return
        self.send_error(404, "File not found")

    def do_HEAD(self) -> None:
        if self._requested_name() == self.server.owner.file_path.name:
            self._serve_file(mark_download_complete=False)
            return
        self.send_error(404, "File not found")


class _HttpServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, owner: "FBIUrlServer", bind_host: str, port: int):
        self.owner = owner
        super().__init__((bind_host, port), _Handler)


class FBIUrlServer:
    """Temporary HTTP server plus FBI Remote Install URL sender."""

    # Match the conventional FBI helper first. Prefer other predictable LAN ports
    # over an arbitrary ephemeral port because local firewalls commonly whitelist
    # application ports while blocking random inbound ports.
    FALLBACK_PORTS = (8000, 8888, 8081)

    def __init__(self, file_path: Path, *, bind_host: str = "0.0.0.0", port: int = 8080):
        self.file_path = file_path.expanduser().resolve()
        if not self.file_path.is_file():
            raise FileNotFoundError(f"CIA file does not exist: {self.file_path}")
        self.bind_host = bind_host
        self.requested_port = port
        self.request_started_event = threading.Event()
        self.served_event = threading.Event()
        self.request_path: str | None = None
        self._request_lock = threading.Lock()
        self._fbi_socket: socket.socket | None = None
        self._ack_thread: threading.Thread | None = None

        ports = []
        if port:
            ports.append(port)
        ports.extend(p for p in self.FALLBACK_PORTS if p not in ports)
        last_error: OSError | None = None
        for candidate in ports:
            try:
                self.httpd = _HttpServer(self, bind_host, candidate)
                break
            except OSError as exc:
                if exc.errno != errno.EADDRINUSE:
                    raise
                last_error = exc
        else:
            # Final fallback if every predictable port is occupied.
            try:
                self.httpd = _HttpServer(self, bind_host, 0)
            except OSError:
                if last_error is not None:
                    raise last_error
                raise

        self.httpd.daemon_threads = True
        self.http_thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1])

    def start(self) -> None:
        self.http_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.http_thread.start()

    def request_started(self) -> None:
        with self._request_lock:
            self.request_path = str(self.file_path.name)
        self.request_started_event.set()

    def request_finished(self) -> None:
        self.served_event.set()

    def local_address(self, preferred_host: str | None = None, peer_host: str | None = None) -> str:
        if preferred_host:
            return preferred_host.strip()
        if peer_host:
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
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
        """Send the FBI URL and return once FBI has accepted the URL payload."""
        three_ds_ip = three_ds_ip.strip()
        if not three_ds_ip:
            raise ValueError("3DS IP address is required for FBI Remote Install.")
        if self._fbi_socket is not None:
            raise RuntimeError("An FBI Remote Install request is already active.")

        sock = socket.create_connection((three_ds_ip, 5000), timeout=timeout)
        try:
            actual_host = host.strip() if host and host.strip() else str(sock.getsockname()[0])
            url = self.url_for(actual_host)
            payload = url.encode("ascii")
            packet = struct.pack("!L", len(payload)) + payload
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

    def wait_for_download(self, timeout: float = 180.0) -> None:
        if self.served_event.wait(0.1):
            return
        if not self.request_started_event.wait(timeout):
            raise TimeoutError(
                f"FBI accepted the URL, but the 3DS never connected to the CIA server at "
                f"http://<PC>:{self.port}. Check the PC address in the generated URL and the PC firewall."
            )
        if not self.served_event.wait(timeout):
            raise TimeoutError("The 3DS connected to the CIA server but did not finish downloading the CIA.")

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
