# SPDX-License-Identifier: Apache-2.0
"""Loopback static assets and explicit test-evidence receiver; no speech inference."""

import argparse
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "android/speech-prototype"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8875)
    parser.add_argument("--run-dir", type=Path, default=ROOT / "artifacts/phonon-pixel-01")
    args = parser.parse_args()
    args.run_dir.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()

    class Handler(SimpleHTTPRequestHandler):
        extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript", ".wasm": "application/wasm"}

        def end_headers(self):
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self' blob:; connect-src 'self'; media-src 'self' blob:; style-src 'self'; object-src 'none'; frame-ancestors 'none'")
            super().end_headers()

        def translate_path(self, path):
            requested = unquote(urlsplit(path).path).lstrip("/") or "index.html"
            if requested.startswith("vendor/"):
                base, requested = WEB / "node_modules/phonon-tts", requested[7:]
            elif requested.startswith("models/"):
                base, requested = WEB / "models", requested[7:]
            else:
                base = WEB
                if requested not in {"index.html", "app.js", "style.css"}:
                    return str(WEB / "not-found")
            resolved = (base / requested).resolve()
            return str(resolved if resolved.is_relative_to(base.resolve()) and resolved.is_file() else WEB / "not-found")

        def log_message(self, format, *values):
            print(format % values, flush=True)

        def do_POST(self):
            allowed = {f"127.0.0.1:{args.port}", f"localhost:{args.port}"}
            origin = self.headers.get("Origin")
            if self.headers.get("Host") not in allowed or origin not in {None, *[f"http://{host}" for host in allowed]}:
                self.send_error(403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 20 * 1024 * 1024:
                    raise ValueError("body size")
                self.connection.settimeout(10)
                body = self.rfile.read(length)
                stamp = datetime.now(timezone.utc).isoformat()
                with lock:
                    if self.path == "/api/event" and self.headers.get_content_type() == "application/json" and length <= 16384:
                        event = json.loads(body)
                        if not isinstance(event, dict):
                            raise ValueError("event must be an object")
                        with (args.run_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
                            stream.write(json.dumps({"received_utc": stamp, **event}, allow_nan=False) + "\n")
                    elif self.path == "/api/test.wav" and body[:4] == b"RIFF" and body[8:12] == b"WAVE":
                        (args.run_dir / "phone-generated.wav").write_bytes(body)
                    else:
                        self.send_error(404)
                        return
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
            except (ValueError, OSError):
                self.send_error(400)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=str(WEB)))
    print(f"Speech experiment: http://127.0.0.1:{args.port}; inference runs in the phone browser", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
