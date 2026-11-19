"""Loopback-only, capability URLs for video playback with byte range support."""

import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class MediaServer:
    def __init__(self):
        self.files = {}
        self.server = None
        self.lock = threading.Lock()

    def url(self, path):
        path = Path(path).resolve()
        if not path.is_file():
            raise ValueError("No encontramos el vídeo en su carpeta.")
        with self.lock:
            if self.server is None:
                owner = self

                class Handler(BaseHTTPRequestHandler):
                    def log_message(self, *args):
                        pass

                    def do_HEAD(self):
                        self.serve(False)

                    def do_GET(self):
                        self.serve(True)

                    def serve(self, body):
                        file = owner.files.get(self.path)
                        if not file or not file.is_file():
                            self.send_error(404)
                            return
                        size = file.stat().st_size
                        start, end, status = 0, size - 1, 200
                        requested = self.headers.get("Range")
                        if requested:
                            match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
                            if not match or not any(match.groups()):
                                self.send_error(416)
                                return
                            a, b = match.groups()
                            if a:
                                start = int(a)
                                end = min(int(b), end) if b else end
                            else:
                                start = max(0, size - int(b))
                            if start >= size or start > end:
                                self.send_response(416)
                                self.send_header("Content-Range", f"bytes */{size}")
                                self.end_headers()
                                return
                            status = 206
                        self.send_response(status)
                        self.send_header("Content-Type", "video/mp4")
                        self.send_header("Accept-Ranges", "bytes")
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("Content-Length", str(end - start + 1))
                        if status == 206:
                            self.send_header(
                                "Content-Range", f"bytes {start}-{end}/{size}"
                            )
                        self.end_headers()
                        if body:
                            try:
                                with file.open("rb") as stream:
                                    stream.seek(start)
                                    remaining = end - start + 1
                                    while remaining > 0:
                                        block = stream.read(min(65536, remaining))
                                        if not block:
                                            break
                                        self.wfile.write(block)
                                        remaining -= len(block)
                            except (
                                BrokenPipeError,
                                ConnectionResetError,
                                ConnectionAbortedError,
                            ):
                                pass

                self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
                threading.Thread(target=self.server.serve_forever, daemon=True).start()
            token = "/" + secrets.token_urlsafe(24) + ".mp4"
            self.files[token] = path
            return f"http://127.0.0.1:{self.server.server_port}{token}"

    def close(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
