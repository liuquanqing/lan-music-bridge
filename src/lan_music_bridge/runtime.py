# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import logging
import mimetypes
import secrets
import threading
import time
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .cache import CacheStore
from .config import Settings
from .control import RendererController
from .discovery import SsdpDiscovery
from .models import PlaybackReceipt, Renderer
from .publishers import load_publisher
from .security import fingerprint, log_event, validate_source_url


class SourceRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._sources: dict[str, tuple[str, float]] = {}

    def register(self, url: str, ttl: float = 6 * 3600) -> str:
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._sources[token] = (url, time.monotonic() + ttl)
        return token

    def resolve(self, token: str) -> str:
        with self._lock:
            self.prune_locked()
            try:
                return self._sources[token][0]
            except KeyError as error:
                raise KeyError("unknown or expired stream token") from error

    def prune_locked(self) -> None:
        now = time.monotonic()
        for token, (_, expires) in list(self._sources.items()):
            if expires <= now:
                self._sources.pop(token, None)

    def count(self) -> int:
        with self._lock:
            self.prune_locked()
            return len(self._sources)


class BridgeRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cache = CacheStore(settings)
        self.discovery = SsdpDiscovery(settings.discovery_source_ip)
        self.controller = RendererController()
        self.publisher = load_publisher(settings, self.cache)
        self.sources = SourceRegistry()
        self.started = time.monotonic()
        self.renderers: list[Renderer] = []
        self.last_protocol = ""
        self.logger = logging.getLogger("lan_music_bridge")

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "version": __version__,
            "uptime_seconds": int(time.monotonic() - self.started),
            "cache": self.cache.stats(),
            "active_stream_tokens": self.sources.count(),
            "renderer_selected": bool(self.renderers),
            "last_protocol": self.last_protocol or None,
        }

    def refresh_renderers(self) -> list[dict[str, object]]:
        self.renderers = self.discovery.discover(self.settings.discovery_timeout)
        log_event(self.logger, "discovery_complete", count=len(self.renderers))
        return [
            {
                "friendly_name": renderer.friendly_name,
                "udn": renderer.udn,
                "protocols": sorted(renderer.services),
            }
            for renderer in self.renderers
        ]

    def _select(self, selector: str) -> Renderer:
        if not self.renderers:
            self.refresh_renderers()
        exact = [item for item in self.renderers if selector in {item.udn, item.friendly_name}]
        if len(exact) != 1:
            raise ValueError("renderer selector must match exactly one discovered device")
        return exact[0]

    def play(
        self,
        selector: str,
        mode: str,
        source: str,
        title: str = "LAN media",
        content_type: str = "",
    ) -> dict[str, str]:
        renderer = self._select(selector)
        normalized = mode.lower()
        if normalized == "stream":
            validate_source_url(source, self.settings)
            if not self.settings.public_base_url:
                raise ValueError("public_base_url is required for stream mode")
            token = self.sources.register(source)
            uri = f"{self.settings.public_base_url.rstrip('/')}/stream/{token}"
            media_fingerprint = fingerprint(source)
            media_type = content_type or "audio/mpeg"
        elif normalized == "local":
            if source.startswith(("http://", "https://")):
                entry = self.cache.ingest_url(source)
            else:
                media_type = content_type or mimetypes.guess_type(source)[0] or "application/octet-stream"
                entry = self.cache.ingest_file(Path(source), media_type)
            uri = self.publisher.publish(entry)
            media_fingerprint = entry.digest[:12]
            media_type = entry.content_type
        else:
            raise ValueError("mode must be stream or local")
        protocol = self.controller.play(renderer, uri, title=title, content_type=media_type)
        self.last_protocol = protocol
        receipt = PlaybackReceipt(
            renderer_id=fingerprint(renderer.udn or renderer.location),
            mode=normalized,
            media_fingerprint=media_fingerprint,
            protocol=protocol,
        )
        log_event(
            self.logger,
            "play_submitted",
            renderer_id=receipt.renderer_id,
            mode=receipt.mode,
            media_fingerprint=receipt.media_fingerprint,
            protocol=receipt.protocol,
        )
        return asdict(receipt)

    def command(self, selector: str, action: str) -> dict[str, str]:
        renderer = self._select(selector)
        protocol = self.controller.command(renderer, action)
        self.last_protocol = protocol
        log_event(
            self.logger,
            "control_submitted",
            renderer_id=fingerprint(renderer.udn or renderer.location),
            action=action,
            protocol=protocol,
        )
        return {"status": "accepted", "action": action, "protocol": protocol}
