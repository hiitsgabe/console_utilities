"""
MJPEG frame streaming wrapper for phone-based dev testing.

Mirrors the pygame display to a phone browser and relays touch events back.
Runs as a standalone entry point — patches pygame.display.flip to capture
frames without requiring any changes to app.py.

Everything runs on a single HTTP port (7654) using multipart MJPEG for
frame delivery and POST for input relay. No extra dependencies needed.

Usage: make stream
"""

import io
import json
import os
import socket
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

import pygame

from constants import SCREEN_WIDTH, SCREEN_HEIGHT

PORT = 7654
TARGET_FPS = 15

# HTML client embedded as string — no separate file needed
CLIENT_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Console Utilities - Stream</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: 100%; height: 100%; background: #000; overflow: hidden; touch-action: none; }
#wrap {
    position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
    -webkit-touch-callout: none; -webkit-user-select: none; user-select: none;
}
#wrap img { display: block; width: 100%; height: 100%; pointer-events: none; -webkit-user-drag: none; }
#status {
    position: fixed; top: 8px; right: 8px; z-index: 10;
    width: 12px; height: 12px; border-radius: 50%;
    background: #f44; transition: background 0.3s;
}
#status.connected { background: #4f4; }
</style>
</head>
<body>
<div id="status"></div>
<div id="wrap"><img id="screen" src="/mjpeg"></div>
<script>
const wrap = document.getElementById('wrap');
const img = document.getElementById('screen');
const status = document.getElementById('status');

const GAME_W = {width};
const GAME_H = {height};

let lastTouchPos = null;

function resize() {
    const ar = GAME_W / GAME_H;
    let w = window.innerWidth;
    let h = window.innerHeight;
    if (w / h > ar) { w = h * ar; } else { h = w / ar; }
    wrap.style.width = w + 'px';
    wrap.style.height = h + 'px';
}
window.addEventListener('resize', resize);
resize();

img.onload = () => { status.className = 'connected'; };
img.onerror = () => { status.className = ''; };

function canvasCoords(clientX, clientY) {
    const rect = wrap.getBoundingClientRect();
    return {
        x: (clientX - rect.left) / rect.width,
        y: (clientY - rect.top) / rect.height
    };
}

function send(obj) {
    fetch('/input', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(obj)
    }).catch(() => {});
}

// Touch events
wrap.addEventListener('touchstart', e => {
    e.preventDefault();
    const t = e.changedTouches[0];
    const c = canvasCoords(t.clientX, t.clientY);
    lastTouchPos = c;
    send({type: 'touchstart', x: c.x, y: c.y});
}, {passive: false});

wrap.addEventListener('touchmove', e => {
    e.preventDefault();
    const t = e.changedTouches[0];
    const c = canvasCoords(t.clientX, t.clientY);
    const prev = lastTouchPos || c;
    send({type: 'touchmove', x: c.x, y: c.y, dx: c.x - prev.x, dy: c.y - prev.y});
    lastTouchPos = c;
}, {passive: false});

wrap.addEventListener('touchend', e => {
    e.preventDefault();
    const t = e.changedTouches[0];
    const c = canvasCoords(t.clientX, t.clientY);
    send({type: 'touchend', x: c.x, y: c.y});
    lastTouchPos = null;
}, {passive: false});

// Mouse events (for desktop browser testing)
let mouseDown = false;
wrap.addEventListener('mousedown', e => {
    mouseDown = true;
    const c = canvasCoords(e.clientX, e.clientY);
    lastTouchPos = c;
    send({type: 'touchstart', x: c.x, y: c.y});
});
wrap.addEventListener('mousemove', e => {
    if (!mouseDown) return;
    const c = canvasCoords(e.clientX, e.clientY);
    const prev = lastTouchPos || c;
    send({type: 'touchmove', x: c.x, y: c.y, dx: c.x - prev.x, dy: c.y - prev.y});
    lastTouchPos = c;
});
wrap.addEventListener('mouseup', e => {
    mouseDown = false;
    const c = canvasCoords(e.clientX, e.clientY);
    send({type: 'touchend', x: c.x, y: c.y});
    lastTouchPos = null;
});
wrap.addEventListener('wheel', e => {
    e.preventDefault();
    send({type: 'wheel', dy: e.deltaY > 0 ? -1 : 1});
}, {passive: false});
</script>
</body>
</html>"""


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


class StreamServer:
    """Streams pygame frames to a browser via MJPEG and relays touch input back."""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self._frame = None
        self._frame_lock = threading.Lock()
        self._frame_event = threading.Event()
        self._html_bytes = (
            CLIENT_HTML.replace("{width}", str(width))
            .replace("{height}", str(height))
            .encode("utf-8")
        )

    def start(self):
        """Start HTTP server in a daemon thread."""
        ip = _get_local_ip()
        print(f"\n  Stream: http://{ip}:{PORT}\n")

        thread = threading.Thread(target=self._run_http, daemon=True)
        thread.start()

    def capture_frame(self, surface):
        """Capture the current pygame surface as JPEG bytes."""
        buf = io.BytesIO()
        try:
            pygame.image.save(surface, buf, "frame.jpg")
        except Exception:
            buf = io.BytesIO()
            pygame.image.save(surface, buf, "frame.png")

        with self._frame_lock:
            self._frame = buf.getvalue()
        self._frame_event.set()

    def _run_http(self):
        """Run the HTTP server."""
        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):
                if self.path == "/mjpeg":
                    self._handle_mjpeg()
                else:
                    self._handle_page()

            def do_POST(self):
                if self.path == "/input":
                    self._handle_input()
                else:
                    self.send_error(404)

            def _handle_page(self):
                body = server_ref._html_bytes
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(body)

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

                interval = 1.0 / TARGET_FPS
                try:
                    while True:
                        server_ref._frame_event.wait(timeout=1.0)
                        server_ref._frame_event.clear()

                        with server_ref._frame_lock:
                            frame = server_ref._frame

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

                        time.sleep(interval)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def _handle_input(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()

                try:
                    data = json.loads(body)
                    server_ref._handle_input(data)
                except (json.JSONDecodeError, KeyError):
                    pass

            def log_message(self, format, *args):
                pass

        class DualStackHTTPServer(ThreadingMixIn, HTTPServer):
            address_family = socket.AF_INET6
            daemon_threads = True

            def server_bind(self):
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                super().server_bind()

        server = DualStackHTTPServer(("::", PORT), Handler)
        server.serve_forever()

    def _handle_input(self, data):
        """Convert browser input to pygame events and inject them."""
        event_type = data.get("type")
        x = int(data.get("x", 0) * self.width)
        y = int(data.get("y", 0) * self.height)

        x = max(0, min(x, self.width - 1))
        y = max(0, min(y, self.height - 1))

        if event_type == "touchstart":
            evt = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(x, y))
            pygame.event.post(evt)

        elif event_type == "touchend":
            evt = pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(x, y))
            pygame.event.post(evt)

        elif event_type == "touchmove":
            dx = int(data.get("dx", 0) * self.width)
            dy = int(data.get("dy", 0) * self.height)
            evt = pygame.event.Event(
                pygame.MOUSEMOTION, pos=(x, y), rel=(dx, dy), buttons=(1, 0, 0)
            )
            pygame.event.post(evt)

        elif event_type == "wheel":
            dy = int(data.get("dy", 0))
            evt = pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=dy)
            pygame.event.post(evt)


def _patch_flip(server):
    """Monkey-patch pygame.display.flip to capture frames after each flip."""
    _original_flip = pygame.display.flip

    def patched_flip():
        _original_flip()
        surface = pygame.display.get_surface()
        if surface:
            server.capture_frame(surface)

    pygame.display.flip = patched_flip


if __name__ == "__main__":
    os.environ["DEV_MODE"] = "true"

    server = StreamServer(SCREEN_WIDTH, SCREEN_HEIGHT)
    server.start()
    _patch_flip(server)

    from app import main

    main()
