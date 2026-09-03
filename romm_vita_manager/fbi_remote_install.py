from __future__ import annotations

import socket
import struct
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return


class FBIUrlServer:
    """Temporary HTTP server plus FBI Remote Install URL sender."""

    def __init__(self, file_path: Path, *, bind_host: str = "0.0.0.0", port: int = 0):
        self.file_path = file_path.expanduser().resolve()
        if not self.file_path.is_file():
            raise FileNotFoundError(f"CIA file does not exist: {self.file_path}")
        self.bind_host = bind_host
        self.httpd = ThreadingHTTPServer((bind_host, port), _QuietHandler)
        self.httpd.daemon_threads = True
        self.http_thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1])

    def start(self) -> None:
        directory = str(self.file_path.parent)
        self.httpd.RequestHandlerClass = lambda *args, **kwargs: _QuietHandler(
            *args, directory=directory, **kwargs
        )
        self.http_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.http_thread.start()

    def local_address(self, preferred_host: str | None = None) -> str:
        if preferred_host:
            return preferred_host
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

    def send_to_fbi(self, three_ds_ip: str, host: str | None = None, timeout: float = 8.0) -> None:
        three_ds_ip = three_ds_ip.strip()
        if not three_ds_ip:
            raise ValueError("3DS IP address is required for FBI Remote Install.")
        url = self.url_for(self.local_address(host))
        payload = url.encode("ascii")
        packet = struct.pack("!L", len(payload)) + payload
        with socket.create_connection((three_ds_ip, 5000), timeout=timeout) as sock:
            sock.sendall(packet)
            sock.settimeout(timeout)
            ack = sock.recv(1)
            if not ack:
                raise TimeoutError("FBI did not acknowledge the remote-install request.")

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        if self.http_thread is not None:
            self.http_thread.join(timeout=2)
            self.http_thread = None

    def __enter__(self) -> "FBIUrlServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
