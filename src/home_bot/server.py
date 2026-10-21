# SPDX-License-Identifier: Apache-2.0
"""Loopback operator panel. Webots APIs stay on the simulation thread."""

from dataclasses import asdict
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit

from .config import RobotConfig
from .control import Command


class Mailbox:
    def __init__(self):
        self.lock = threading.Lock()
        self.pending: tuple[Command, float] | None = None
        self.state: dict = {"status": "starting"}
        self.camera: bytes = b""
        self.observation: dict | None = None

    def submit(self, command: Command) -> None:
        with self.lock:
            self.pending = (command, time.monotonic())

    def take(self) -> tuple[Command, float] | None:
        with self.lock:
            pending, self.pending = self.pending, None
            return pending

    def publish(self, state: dict, camera: bytes | None = None) -> None:
        with self.lock:
            self.state = state
            if camera is not None:
                self.camera = camera
                self.observation = {"state": state, "camera_png_base64": base64.b64encode(camera).decode("ascii")}


def start_server(mailbox: Mailbox, config: RobotConfig) -> ThreadingHTTPServer:
    web = Path(__file__).parent / "web"
    static = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
              "/style.css": ("style.css", "text/css")}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, status: int, body: bytes, content_type: str = "application/json") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def do_GET(self):
            path = urlsplit(self.path).path
            if path in static:
                name, mime = static[path]
                self.reply(200, (web / name).read_bytes(), mime + "; charset=utf-8")
            elif path == "/api/state":
                with mailbox.lock:
                    state = mailbox.state
                self.reply(200, json.dumps(state, allow_nan=False).encode())
            elif path == "/api/camera.png":
                with mailbox.lock:
                    frame = mailbox.camera
                self.reply(200 if frame else 503, frame or b'{"error":"camera not ready"}', "image/png" if frame else "application/json")
            elif path == "/api/observation":
                with mailbox.lock:
                    observation = mailbox.observation
                self.reply(200 if observation else 503, json.dumps(observation or {"error": "camera not ready"}, allow_nan=False).encode())
            else:
                self.reply(404, b'{"error":"not found"}')

        def do_POST(self):
            if self.path != "/api/command":
                self.reply(404, b'{"error":"not found"}')
                return
            # A loopback service must also reject commands from unrelated web pages.
            allowed_hosts = {f"127.0.0.1:{config.http_port}", f"localhost:{config.http_port}"}
            origin = self.headers.get("Origin")
            if self.headers.get("Host") not in allowed_hosts or (origin is not None and origin not in {f"http://{host}" for host in allowed_hosts}):
                self.reply(403, b'{"error":"same-origin commands only"}')
                return
            try:
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("Content-Type must be application/json")
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 4096:
                    raise ValueError("Command body must contain 1..4096 bytes")
                self.connection.settimeout(2)
                body = self.rfile.read(length)
                command = Command.parse(json.loads(body), config)
            except (ValueError, UnicodeDecodeError, TimeoutError) as error:
                self.reply(400, json.dumps({"error": str(error)}).encode())
                return
            mailbox.submit(command)
            self.reply(202, json.dumps({"accepted": asdict(command)}).encode())

    server = ThreadingHTTPServer((config.http_host, config.http_port), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, name="operator-panel", daemon=True)
    thread.start()
    return server
