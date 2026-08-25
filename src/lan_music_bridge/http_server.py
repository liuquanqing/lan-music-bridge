# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import http.server
import ipaddress
import json
import logging
import re
import threading

from . import __version__
from .control import QueueMutationError, QueueUnsupportedError
from .net import open_source
from .runtime import BridgeRuntime
from .security import fingerprint, log_event, validate_source_url

RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


def parse_byte_range(value: str, size: int) -> tuple[int, int, bool]:
    if not value:
        return 0, max(0, size - 1), False
    match = RANGE.fullmatch(value.strip())
    if not match or size <= 0:
        raise ValueError("invalid byte range")
    first, last = match.groups()
    if not first:
        length = int(last)
        if length <= 0:
            raise ValueError("invalid suffix range")
        start = max(0, size - length)
        end = size - 1
    else:
        start = int(first)
        end = int(last) if last else size - 1
    if start >= size or end < start:
        raise ValueError("range is outside media")
    return start, min(end, size - 1), True


class BridgeHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, runtime: BridgeRuntime):  # noqa: ANN001
        super().__init__(address, handler)
        self.runtime = runtime


class BaseHandler(http.server.BaseHTTPRequestHandler):
    server_version = f"lan-music-bridge/{__version__}"
    sys_version = ""

    @property
    def runtime(self) -> BridgeRuntime:
        return self.server.runtime  # type: ignore[attr-defined]

    def log_message(self, format_string: str, *args: object) -> None:
        route = self.path.split("?", 1)[0]
        if route.startswith("/stream/"):
            route = "/stream/<redacted>"
        elif route.startswith("/media/"):
            route = "/media/<digest>"
        status = str(args[1]) if len(args) > 1 else ""
        log_event(
            logging.getLogger("lan_music_bridge.http"),
            "http_request",
            peer_fingerprint=fingerprint(self.client_address[0]),
            method=self.command,
            route=route,
            status=status,
        )

    def send_body(
        self,
        status: int,
        content_type: str,
        body: bytes,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, status: int, value: object) -> None:
        self.send_body(
            status,
            "application/json; charset=utf-8",
            json.dumps(value, ensure_ascii=True, sort_keys=True).encode("utf-8"),
            {"Cache-Control": "no-store"},
        )


class MediaHandler(BaseHandler):
    def do_GET(self) -> None:
        route = self.path.split("?", 1)[0]
        if route == "/health":
            self.send_json(200, self.runtime.health())
            return
        if route == "/ready":
            self.send_json(200, {"status": "ready"})
            return
        if route.startswith("/media/"):
            self._serve_cached(route.rsplit("/", 1)[-1])
            return
        if route.startswith("/stream/"):
            self._serve_stream(route.rsplit("/", 1)[-1])
            return
        self.send_body(404, "text/plain; charset=utf-8", b"not found")

    do_HEAD = do_GET

    def _serve_cached(self, digest: str) -> None:
        try:
            entry = self.runtime.cache.get(digest)
            start, end, partial = parse_byte_range(
                self.headers.get("Range", ""), entry.size
            )
        except KeyError:
            self.send_body(404, "text/plain; charset=utf-8", b"media not found")
            return
        except ValueError:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{entry.size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        length = end - start + 1
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", entry.content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.send_header("X-Content-Type-Options", "nosniff")
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{entry.size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with entry.path.open("rb") as source:
            source.seek(start)
            remaining = length
            while remaining:
                block = source.read(min(1024 * 1024, remaining))
                if not block:
                    break
                self.wfile.write(block)
                remaining -= len(block)

    def _serve_stream(self, token: str) -> None:
        try:
            source_url = self.runtime.sources.resolve(token)
            validate_source_url(source_url, self.runtime.settings)
            upstream_headers = {}
            if self.headers.get("Range"):
                upstream_headers["Range"] = self.headers["Range"]
            with open_source(
                source_url,
                self.runtime.settings,
                headers=upstream_headers,
                timeout=20,
            ) as response:
                self.send_response(response.status)
                self.send_header("Content-Type", response.headers.get_content_type())
                self.send_header("Accept-Ranges", "bytes")
                for header in ("Content-Length", "Content-Range"):
                    if response.headers.get(header):
                        self.send_header(header, response.headers[header])
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                if self.command == "HEAD":
                    return
                while True:
                    block = response.read(64 * 1024)
                    if not block:
                        break
                    self.wfile.write(block)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as error:
            log_event(
                logging.getLogger("lan_music_bridge.http"),
                "stream_failed",
                token_fingerprint=fingerprint(token),
                error_type=type(error).__name__,
            )
            self.send_body(502, "text/plain; charset=utf-8", b"upstream unavailable")


class AdminHandler(BaseHandler):
    def _is_loopback(self) -> bool:
        try:
            return ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            return False

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > 1024 * 1024:
            raise ValueError("invalid request size")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("JSON object required")
        return value

    def do_GET(self) -> None:
        if not self._is_loopback():
            self.send_body(403, "text/plain; charset=utf-8", b"forbidden")
            return
        if self.path.split("?", 1)[0] == "/v1/status":
            self.send_json(200, self.runtime.health())
            return
        self.send_body(404, "text/plain; charset=utf-8", b"not found")

    def do_POST(self) -> None:
        if not self._is_loopback():
            self.send_body(403, "text/plain; charset=utf-8", b"forbidden")
            return
        route = self.path.split("?", 1)[0]
        try:
            payload = self._read_json()
            if route == "/v1/discover":
                result: object = {"renderers": self.runtime.refresh_renderers()}
            elif route == "/v1/play":
                result = self.runtime.play(
                    selector=str(payload.get("renderer", "")),
                    mode=str(payload.get("mode", "")),
                    source=str(payload.get("source", "")),
                    title=str(payload.get("title", "LAN media")),
                    content_type=str(payload.get("content_type", "")),
                )
            elif route == "/v1/queue":
                result = self.runtime.queue(
                    selector=str(payload.get("renderer", "")),
                    items=payload.get("items"),
                )
            elif route == "/v1/control":
                result = self.runtime.command(
                    selector=str(payload.get("renderer", "")),
                    action=str(payload.get("action", "")),
                )
            else:
                self.send_body(404, "text/plain; charset=utf-8", b"not found")
                return
            self.send_json(200, result)
        except QueueUnsupportedError as error:
            log_event(
                logging.getLogger("lan_music_bridge.admin"),
                "admin_request_failed",
                route=route,
                error_type=type(error).__name__,
            )
            self.send_json(
                422,
                {"error": "multi-track queue requires OpenHome Playlist"},
            )
        except QueueMutationError as error:
            log_event(
                logging.getLogger("lan_music_bridge.admin"),
                "admin_request_failed",
                route=route,
                error_type=type(error).__name__,
            )
            self.send_json(
                409,
                {
                    "error": "renderer queue update failed",
                    "device_queue_may_be_partial": True,
                },
            )
        except Exception as error:
            log_event(
                logging.getLogger("lan_music_bridge.admin"),
                "admin_request_failed",
                route=route,
                error_type=type(error).__name__,
            )
            self.send_json(400, {"error": "request rejected"})


class BridgeServers:
    def __init__(self, runtime: BridgeRuntime):
        self.runtime = runtime
        settings = runtime.settings
        self.media = BridgeHTTPServer(
            (settings.media_host, settings.media_port), MediaHandler, runtime
        )
        self.admin = BridgeHTTPServer(
            (settings.admin_host, settings.admin_port), AdminHandler, runtime
        )
        self._media_thread = threading.Thread(
            target=self.media.serve_forever, name="media-http", daemon=True
        )

    def serve_forever(self) -> None:
        self._media_thread.start()
        self.admin.serve_forever()

    def shutdown(self) -> None:
        self.admin.shutdown()
        self.media.shutdown()
        self.admin.server_close()
        self.media.server_close()
