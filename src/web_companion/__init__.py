"""
Web Companion server for Console Utilities.

Runs an HTTP server alongside PyGame so the user can open a phone browser
on the same network and get a context-aware web interface for faster input.
"""

import io
import json
import os
import queue
import shutil
import socket
import threading
import time
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

import pygame

from constants import SCREEN_WIDTH, SCREEN_HEIGHT, WEB_COMPANION_PORT
from .state_serializer import serialize_web_state
from .action_handler import handle_action
from .client import CLIENT_HTML


def _get_local_ip():
    """Get the local network IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


class WebCompanion:
    """
    Web companion server that provides a phone-friendly UI alongside PyGame.

    Streams state via SSE, receives actions via POST, and optionally
    streams MJPEG frames for a live thumbnail of the handheld screen.
    """

    def __init__(self, port=WEB_COMPANION_PORT):
        self.port = port
        self._action_queue = queue.Queue()
        self._state_json = "{}"
        self._state_lock = threading.Lock()
        self._state_event = threading.Event()
        self._frame = None
        self._frame_lock = threading.Lock()
        self._frame_event = threading.Event()
        self._server = None
        self._thread = None
        self._running = False
        self._html_bytes = CLIENT_HTML.encode("utf-8")
        self._local_ip = _get_local_ip()
        self._settings = None

    @property
    def url(self):
        return f"http://{self._local_ip}:{self.port}"

    def start(self):
        """Start the web companion server in a daemon thread."""
        if self._running:
            return
        self._running = True
        self._local_ip = _get_local_ip()
        print(f"\n  Web Companion: {self.url}\n")
        self._thread = threading.Thread(target=self._run_http, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the web companion server."""
        self._running = False
        if self._server:
            self._server.shutdown()
            self._server = None
        self._thread = None

    def push_state(self, state, settings=None, data=None):
        """Serialize and push state to connected SSE clients (throttled)."""
        if settings is not None:
            self._settings = settings
        try:
            state_dict = serialize_web_state(state, settings, data)
            state_json = json.dumps(state_dict, default=str)
            with self._state_lock:
                self._state_json = state_json
            self._state_event.set()
        except Exception:
            pass

    def capture_frame(self, surface):
        """Capture the current pygame surface as JPEG bytes for MJPEG stream."""
        buf = io.BytesIO()
        try:
            pygame.image.save(surface, buf, "frame.jpg")
        except Exception:
            buf = io.BytesIO()
            pygame.image.save(surface, buf, "frame.png")
        with self._frame_lock:
            self._frame = buf.getvalue()
        self._frame_event.set()

    def process_actions(self, state):
        """Drain the action queue and apply actions to app state."""
        while not self._action_queue.empty():
            try:
                action_data = self._action_queue.get_nowait()
                handle_action(state, action_data)
            except queue.Empty:
                break
            except Exception:
                pass

    def _run_http(self):
        """Run the HTTP server."""
        companion = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):
                if self.path == "/events":
                    self._handle_sse()
                elif self.path == "/mjpeg":
                    self._handle_mjpeg()
                elif self.path == "/api/files/config":
                    self._handle_file_config()
                elif self.path.startswith("/api/files/download"):
                    self._handle_file_download()
                elif self.path.startswith("/api/files"):
                    self._handle_file_list()
                else:
                    self._handle_page()

            def do_POST(self):
                if self.path == "/action":
                    self._handle_action()
                elif self.path.startswith("/api/files/upload"):
                    self._handle_file_upload()
                elif self.path == "/api/files/mkdir":
                    self._handle_file_mkdir()
                elif self.path == "/api/files/delete":
                    self._handle_file_delete()
                elif self.path == "/api/files/rename":
                    self._handle_file_rename()
                else:
                    self.send_error(404)

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def _handle_page(self):
                body = companion._html_bytes
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.send_header("Pragma", "no-cache")
                self.end_headers()
                self.wfile.write(body)

            def _handle_sse(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                last_json = None
                try:
                    while companion._running:
                        companion._state_event.wait(timeout=1.0)
                        companion._state_event.clear()

                        with companion._state_lock:
                            current_json = companion._state_json

                        if current_json != last_json:
                            last_json = current_json
                            msg = f"data: {current_json}\n\n"
                            self.wfile.write(msg.encode("utf-8"))
                            self.wfile.flush()

                        time.sleep(0.1)  # Throttle to ~10/sec
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

            def _handle_mjpeg(self):
                boundary = b"--frame"
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "multipart/x-mixed-replace; boundary=frame",
                )
                self.send_header("Cache-Control", "no-cache, no-store")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                try:
                    while companion._running:
                        companion._frame_event.wait(timeout=1.0)
                        companion._frame_event.clear()

                        with companion._frame_lock:
                            frame = companion._frame

                        if frame:
                            self.wfile.write(
                                boundary + b"\r\n"
                                b"Content-Type: image/jpeg\r\n"
                                b"Content-Length: "
                                + str(len(frame)).encode()
                                + b"\r\n\r\n"
                                + frame
                                + b"\r\n"
                            )
                            self.wfile.flush()

                        time.sleep(1.0 / 15)  # ~15 FPS
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

            def _handle_action(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                response = b'{"ok":true}'
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

                try:
                    data = json.loads(body)
                    companion._action_queue.put(data)
                except (json.JSONDecodeError, KeyError):
                    pass

            # ---- File Manager API handlers ----

            def _parse_query_param(self, param):
                """Extract a query parameter from self.path."""
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)
                values = params.get(param, [])
                return values[0] if values else None

            def _send_json(self, obj, status=200):
                body = json.dumps(obj, default=str).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)

            def _send_error_json(self, msg, status=400):
                self._send_json({"error": msg}, status)

            def _safe_path(self, path):
                """Resolve path and ensure it's within allowed roots."""
                if not path:
                    return None
                # Normalize and resolve
                resolved = os.path.realpath(os.path.expanduser(path))
                return resolved

            def _handle_file_config(self):
                """GET /api/files/config - Return file manager config."""
                settings = companion._settings or {}
                roms_dir = settings.get("roms_dir", "/")
                if not roms_dir or not os.path.isdir(roms_dir):
                    roms_dir = "/"
                self._send_json({"roms_dir": roms_dir})

            def _handle_file_list(self):
                """GET /api/files?path=... - List directory contents."""
                path = self._parse_query_param("path") or "/"
                resolved = self._safe_path(path)
                if not resolved or not os.path.isdir(resolved):
                    self._send_error_json(
                        "Directory not found: " + (path or ""), 404
                    )
                    return

                entries = []
                try:
                    with os.scandir(resolved) as it:
                        for entry in it:
                            # Skip hidden files on Unix
                            if entry.name.startswith("."):
                                continue
                            try:
                                stat = entry.stat()
                                entries.append(
                                    {
                                        "name": entry.name,
                                        "is_dir": entry.is_dir(),
                                        "size": stat.st_size
                                        if not entry.is_dir()
                                        else None,
                                        "modified": stat.st_mtime,
                                    }
                                )
                            except OSError:
                                entries.append(
                                    {
                                        "name": entry.name,
                                        "is_dir": entry.is_dir(),
                                        "size": None,
                                        "modified": None,
                                    }
                                )
                except PermissionError:
                    self._send_error_json("Permission denied", 403)
                    return

                # Sort: folders first, then alphabetical
                entries.sort(
                    key=lambda e: (
                        0 if e["is_dir"] else 1,
                        e["name"].lower(),
                    )
                )

                self._send_json({"path": resolved, "entries": entries})

            def _handle_file_download(self):
                """GET /api/files/download?path=... - Download a file."""
                path = self._parse_query_param("path")
                resolved = self._safe_path(path)
                if not resolved or not os.path.isfile(resolved):
                    self._send_error_json("File not found", 404)
                    return

                try:
                    file_size = os.path.getsize(resolved)
                    filename = os.path.basename(resolved)
                    self.send_response(200)
                    self.send_header(
                        "Content-Type", "application/octet-stream"
                    )
                    self.send_header("Content-Length", str(file_size))
                    self.send_header(
                        "Content-Disposition",
                        f'attachment; filename="{filename}"',
                    )
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()

                    with open(resolved, "rb") as f:
                        while True:
                            chunk = f.read(65536)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                except (OSError, BrokenPipeError) as e:
                    pass

            def _handle_file_upload(self):
                """POST /api/files/upload?path=... - Upload files."""
                dest_dir = self._parse_query_param("path") or "/"
                resolved_dir = self._safe_path(dest_dir)
                if not resolved_dir or not os.path.isdir(resolved_dir):
                    self._send_error_json("Destination not found", 404)
                    return

                content_type = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in content_type:
                    self._send_error_json("Expected multipart/form-data")
                    return

                try:
                    # Extract boundary from Content-Type
                    boundary = None
                    for part in content_type.split(";"):
                        part = part.strip()
                        if part.startswith("boundary="):
                            boundary = part[9:].strip().strip('"')
                            break
                    if not boundary:
                        self._send_error_json("No boundary in Content-Type")
                        return

                    content_length = int(
                        self.headers.get("Content-Length", 0)
                    )
                    body = self.rfile.read(content_length)
                    boundary_bytes = boundary.encode("utf-8")

                    uploaded = []
                    # Split by boundary
                    parts = body.split(b"--" + boundary_bytes)
                    for part in parts:
                        if not part or part.strip() in (b"", b"--"):
                            continue
                        # Remove trailing --\r\n if this is the last part
                        if part.startswith(b"--"):
                            continue

                        # Split headers from body (separated by \r\n\r\n)
                        header_end = part.find(b"\r\n\r\n")
                        if header_end < 0:
                            continue
                        header_data = part[: header_end].decode(
                            "utf-8", errors="replace"
                        )
                        file_data = part[header_end + 4 :]
                        # Strip trailing \r\n
                        if file_data.endswith(b"\r\n"):
                            file_data = file_data[:-2]

                        # Parse Content-Disposition for filename
                        filename = None
                        for line in header_data.split("\r\n"):
                            if line.lower().startswith(
                                "content-disposition:"
                            ):
                                for token in line.split(";"):
                                    token = token.strip()
                                    if token.startswith("filename="):
                                        filename = token[9:].strip('"')
                                        break

                        if filename:
                            filename = os.path.basename(filename)
                            dest_path = os.path.join(
                                resolved_dir, filename
                            )
                            with open(dest_path, "wb") as f:
                                f.write(file_data)
                            uploaded.append(filename)

                    self._send_json({"ok": True, "uploaded": uploaded})
                except Exception as e:
                    self._send_error_json(str(e), 500)

            def _handle_file_mkdir(self):
                """POST /api/files/mkdir - Create directory."""
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    self._send_error_json("Invalid JSON")
                    return

                path = data.get("path")
                resolved = self._safe_path(path)
                if not resolved:
                    self._send_error_json("Invalid path")
                    return

                try:
                    os.makedirs(resolved, exist_ok=True)
                    self._send_json({"ok": True, "path": resolved})
                except OSError as e:
                    self._send_error_json(str(e), 500)

            def _handle_file_delete(self):
                """POST /api/files/delete - Delete file or directory."""
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    self._send_error_json("Invalid JSON")
                    return

                path = data.get("path")
                resolved = self._safe_path(path)
                if not resolved:
                    self._send_error_json("Invalid path")
                    return

                if not os.path.exists(resolved):
                    self._send_error_json("Not found", 404)
                    return

                try:
                    if os.path.isdir(resolved):
                        shutil.rmtree(resolved)
                    else:
                        os.remove(resolved)
                    self._send_json({"ok": True})
                except OSError as e:
                    self._send_error_json(str(e), 500)

            def _handle_file_rename(self):
                """POST /api/files/rename - Rename file or directory."""
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    self._send_error_json("Invalid JSON")
                    return

                path = data.get("path")
                new_name = data.get("name")
                if not path or not new_name:
                    self._send_error_json("Missing path or name")
                    return

                resolved = self._safe_path(path)
                if not resolved or not os.path.exists(resolved):
                    self._send_error_json("Not found", 404)
                    return

                # Prevent directory traversal in new name
                if "/" in new_name or "\\" in new_name:
                    self._send_error_json("Invalid name")
                    return

                parent = os.path.dirname(resolved)
                new_path = os.path.join(parent, new_name)
                try:
                    os.rename(resolved, new_path)
                    self._send_json({"ok": True, "path": new_path})
                except OSError as e:
                    self._send_error_json(str(e), 500)

            def log_message(self, format, *args):
                pass

        class DualStackHTTPServer(ThreadingMixIn, HTTPServer):
            daemon_threads = True

            def server_bind(self):
                try:
                    self.address_family = socket.AF_INET6
                    self.socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    self.socket.setsockopt(
                        socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0
                    )
                    self.socket.bind(self.server_address)
                    self.server_address = self.socket.getsockname()[:2]
                except Exception:
                    # Fallback to IPv4
                    self.address_family = socket.AF_INET
                    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    self.server_address = ("0.0.0.0", self.server_address[1])
                    self.socket.bind(self.server_address)
                    self.server_address = self.socket.getsockname()[:2]

        try:
            companion._server = DualStackHTTPServer(("::", self.port), Handler)
            companion._server.serve_forever()
        except Exception:
            # Fallback
            try:
                companion._server = HTTPServer(("0.0.0.0", self.port), Handler)
                companion._server.serve_forever()
            except Exception as e:
                print(f"Web Companion failed to start: {e}")
