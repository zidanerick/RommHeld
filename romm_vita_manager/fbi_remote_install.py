from __future__ import annotations

import errno
import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote


FBI_HTTP_PORT = 8080


class _Handler(BaseHTTPRequestHandler):
    server: "_HttpServer"

    def setup(self) -> None:
        super().setup()
        try:
            # FBI pulls large CIA payloads over one long-lived TCP stream. A
            # larger send buffer reduces avoidable stalls on fast LAN links;
            # the OS may clamp this to its configured maximum.
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024)
        except OSError:
            pass

    def log_message(self, format: str, *args) -> None:
        return

    def _send_payload(self, source: Path) -> None:
        """Send the CIA with the kernel sendfile path when available."""
        with source.open("rb") as handle:
            try:
                self.connection.sendfile(handle)
                return
            except (AttributeError, NotImplementedError):
                # socket.sendfile is not available on every Python/platform.
                pass

            # Keep a large userspace fallback for platforms without sendfile.
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def _serve_file(self, *, track_download: bool) -> None:
        source = self.server.owner.file_path
        try:
            size = source.stat().st_size
        except OSError as exc:
            self.send_error(404, str(exc))
            return

        if track_download:
            self.server.owner.request_started()

        completed = False
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command == "HEAD":
                completed = True
                return
            self._send_payload(source)
            completed = True
        finally:
            if track_download:
                self.server.owner.request_finished(completed)

    def _requested_name(self) -> str:
        return self.path.split("?", 1)[0].lstrip("/")

    def do_GET(self) -> None:
        if self._requested_name() != self.server.owner.file_path.name:
            self.send_error(404, "File not found")
            return
        try:
            self._serve_file(track_download=True)
        except (BrokenPipeError, ConnectionResetError):
            # _serve_file() records the interrupted request in its finally block.
            return

    def do_HEAD(self) -> None:
        if self._requested_name() == self.server.owner.file_path.name:
            self._serve_file(track_download=False)
            return
        self.send_error(404, "File not found")


class _HttpServer(ThreadingHTTPServer):
    allow_reuse_address = True
    request_queue_size = 8

    def __init__(self, owner: "FBIUrlServer", bind_host: str, port: int):
        self.owner = owner
        super().__init__((bind_host, port), _Handler)


class FBIUrlServer:
    """HTTP server plus FBI Remote Install URL sender.

    Port 8080 remains the preferred stable port so RommHeld can create one
    persistent, narrowly-scoped firewall rule and reuse it across transfers.
    Fallback ports are retained for compatibility when another process already
    owns 8080; callers should pass the resulting ``port`` to the firewall
    helper so that fallback rule is remembered as well.
    """

    FALLBACK_PORTS = (8000, 8888, 8081)

    def __init__(self, file_path: Path, *, bind_host: str = "0.0.0.0", port: int = FBI_HTTP_PORT):
        self.file_path = file_path.expanduser().resolve()
        if not self.file_path.is_file():
            raise FileNotFoundError(f"CIA file does not exist: {self.file_path}")
        self.bind_host = bind_host
        self.requested_port = port
        self.request_started_event = threading.Event()
        self.served_event = threading.Event()
        self.request_failed_event = threading.Event()
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
        self.request_failed_event.clear()

    def request_finished(self, success: bool) -> None:
        if success:
            self.served_event.set()
            self.request_failed_event.clear()
        else:
            self.request_failed_event.set()

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
        """Send the FBI URL and return once the URL payload is handed to FBI."""
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

    def wait_for_download(self, timeout: float = 600.0, cancel_event: threading.Event | None = None) -> None:
        elapsed = 0.0
        sleeper = threading.Event()
        while not self.request_started_event.is_set():
            if self.served_event.is_set():
                return
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError
            if elapsed >= timeout:
                raise TimeoutError(
                    f"FBI accepted the URL, but the 3DS never connected to the CIA server at "
                    f"http://<PC>:{self.port}. Check the PC address in the generated URL and the PC firewall."
                )
            sleeper.wait(0.25)
            elapsed += 0.25

        elapsed = 0.0
        while not self.served_event.is_set():
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError
            if self.request_failed_event.is_set():
                raise ConnectionError(
                    "The 3DS connected to the CIA server, but the HTTP transfer ended before the complete CIA was sent."
                )
            if elapsed >= timeout:
                raise TimeoutError("The 3DS connected to the CIA server but did not finish downloading the CIA.")
            sleeper.wait(0.25)
            elapsed += 0.25

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
