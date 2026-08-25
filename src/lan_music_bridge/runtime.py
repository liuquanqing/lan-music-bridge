# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import logging
import mimetypes
import secrets
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from . import __version__
from .cache import CacheStore
from .config import Settings
from .control import (
    ControlError,
    QueueMutationError,
    QueueUnsupportedError,
    RendererController,
)
from .discovery import SsdpDiscovery
from .models import PlaybackReceipt, PreparedTrack, Renderer
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

    def discard(self, token: str) -> None:
        with self._lock:
            self._sources.pop(token, None)

    def prune_locked(self) -> None:
        now = time.monotonic()
        for token, (_, expires) in list(self._sources.items()):
            if expires <= now:
                self._sources.pop(token, None)

    def count(self) -> int:
        with self._lock:
            self.prune_locked()
            return len(self._sources)


class RendererIntentSuperseded(RuntimeError):
    """An older renderer intent finished preparing after a newer request arrived."""


MAX_QUEUE_ITEMS = 100


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
        self._intent_state_lock = threading.Lock()
        self._intent_generations: dict[str, int] = {}
        self._intent_apply_locks: dict[str, threading.Lock] = {}

    def _begin_renderer_intent(
        self, renderer: Renderer
    ) -> tuple[str, int, threading.Lock]:
        key = renderer.udn or renderer.location
        with self._intent_state_lock:
            generation = self._intent_generations.get(key, 0) + 1
            self._intent_generations[key] = generation
            apply_lock = self._intent_apply_locks.setdefault(key, threading.Lock())
        return key, generation, apply_lock

    def _apply_current_intent(
        self,
        key: str,
        generation: int,
        apply_lock: threading.Lock,
        operation: Callable[[], str],
    ) -> str:
        with apply_lock:
            with self._intent_state_lock:
                if self._intent_generations.get(key) != generation:
                    raise RendererIntentSuperseded("renderer intent was superseded")
            return operation()

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

    def _validate_item(self, item: object) -> dict[str, str]:
        if not isinstance(item, dict):
            raise ValueError("each queue item must be a JSON object")
        unknown = set(item) - {"mode", "source", "title", "content_type"}
        if unknown:
            raise ValueError("queue item contains unsupported fields")
        mode = item.get("mode")
        source = item.get("source")
        title = item.get("title", "LAN media")
        content_type = item.get("content_type", "")
        if mode not in {"stream", "local"}:
            raise ValueError("queue item mode must be stream or local")
        if not isinstance(source, str) or not source or len(source) > 8192:
            raise ValueError("queue item source is invalid")
        if not isinstance(title, str) or not title or len(title) > 512:
            raise ValueError("queue item title is invalid")
        if not isinstance(content_type, str) or len(content_type) > 255:
            raise ValueError("queue item content_type is invalid")
        if mode == "stream":
            validate_source_url(source, self.settings)
            if not self.settings.public_base_url:
                raise ValueError("public_base_url is required for stream mode")
        return {
            "mode": mode,
            "source": source,
            "title": title,
            "content_type": content_type,
        }

    def _prepare_item(self, item: dict[str, str]) -> PreparedTrack:
        mode = item["mode"]
        source = item["source"]
        content_type = item["content_type"]
        if mode == "stream":
            token = self.sources.register(source)
            return PreparedTrack(
                uri=f"{self.settings.public_base_url.rstrip('/')}/stream/{token}",
                title=item["title"],
                content_type=content_type or "audio/mpeg",
                mode=mode,
                media_fingerprint=fingerprint(source),
                stream_token=token,
            )
        if source.startswith(("http://", "https://")):
            entry = self.cache.ingest_url(source)
        else:
            inferred_type = (
                content_type
                or mimetypes.guess_type(source)[0]
                or "application/octet-stream"
            )
            entry = self.cache.ingest_file(Path(source), inferred_type)
        return PreparedTrack(
            uri=self.publisher.publish(entry),
            title=item["title"],
            content_type=content_type or entry.content_type,
            mode=mode,
            media_fingerprint=entry.digest[:12],
        )

    def _discard_stream_tokens(self, tracks: list[PreparedTrack]) -> None:
        for track in tracks:
            if track.stream_token:
                self.sources.discard(track.stream_token)

    def queue(
        self,
        selector: str,
        items: object,
    ) -> dict[str, object]:
        renderer = self._select(selector)
        if not isinstance(items, list) or not items:
            raise ValueError("queue items must be a non-empty JSON array")
        if len(items) > MAX_QUEUE_ITEMS:
            raise ValueError(f"queue cannot exceed {MAX_QUEUE_ITEMS} items")
        if not renderer.service("urn:av-openhome-org:service:Playlist:"):
            raise QueueUnsupportedError(
                "multi-track queues require an OpenHome Playlist service"
            )
        validated = [self._validate_item(item) for item in items]

        intent_key, generation, apply_lock = self._begin_renderer_intent(renderer)
        prepared: list[PreparedTrack] = []
        try:
            for item in validated:
                prepared.append(self._prepare_item(item))
            protocol = self._apply_current_intent(
                intent_key,
                generation,
                apply_lock,
                lambda: self.controller.replace_queue(renderer, tuple(prepared)),
            )
        except QueueMutationError:
            # The renderer may already reference one or more prepared token URLs.
            # Keep them alive for their normal six-hour TTL and report partial state.
            log_event(
                self.logger,
                "queue_mutation_failed",
                renderer_id=fingerprint(renderer.udn or renderer.location),
                item_count=len(prepared),
            )
            raise
        except Exception as error:
            self._discard_stream_tokens(prepared)
            event = (
                "queue_superseded"
                if isinstance(error, RendererIntentSuperseded)
                else "queue_preparation_failed"
            )
            log_event(
                self.logger,
                event,
                renderer_id=fingerprint(renderer.udn or renderer.location),
                prepared_count=len(prepared),
            )
            raise

        self.last_protocol = protocol
        renderer_id = fingerprint(renderer.udn or renderer.location)
        log_event(
            self.logger,
            "queue_submitted",
            renderer_id=renderer_id,
            item_count=len(prepared),
            protocol=protocol,
        )
        return {
            "status": "accepted",
            "renderer_id": renderer_id,
            "item_count": len(prepared),
            "protocol": protocol,
        }

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
        if normalized not in {"stream", "local"}:
            raise ValueError("mode must be stream or local")
        if not source:
            raise ValueError("media source is required")
        if normalized == "stream":
            validate_source_url(source, self.settings)
            if not self.settings.public_base_url:
                raise ValueError("public_base_url is required for stream mode")
        intent_key, generation, apply_lock = self._begin_renderer_intent(renderer)
        stream_token = ""
        if normalized == "stream":
            stream_token = self.sources.register(source)
            uri = f"{self.settings.public_base_url.rstrip('/')}/stream/{stream_token}"
            media_fingerprint = fingerprint(source)
            media_type = content_type or "audio/mpeg"
        else:
            if source.startswith(("http://", "https://")):
                entry = self.cache.ingest_url(source)
            else:
                media_type = content_type or mimetypes.guess_type(source)[0] or "application/octet-stream"
                entry = self.cache.ingest_file(Path(source), media_type)
            uri = self.publisher.publish(entry)
            media_fingerprint = entry.digest[:12]
            media_type = entry.content_type
        try:
            protocol = self._apply_current_intent(
                intent_key,
                generation,
                apply_lock,
                lambda: self.controller.play(
                    renderer, uri, title=title, content_type=media_type
                ),
            )
        except RendererIntentSuperseded:
            if stream_token:
                self.sources.discard(stream_token)
            log_event(
                self.logger,
                "play_superseded",
                renderer_id=fingerprint(renderer.udn or renderer.location),
                mode=normalized,
                media_fingerprint=media_fingerprint,
            )
            raise
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
        if action.lower() not in {"play", "pause", "stop"}:
            raise ControlError("unsupported command")
        intent_key, generation, apply_lock = self._begin_renderer_intent(renderer)
        protocol = self._apply_current_intent(
            intent_key,
            generation,
            apply_lock,
            lambda: self.controller.command(renderer, action),
        )
        self.last_protocol = protocol
        log_event(
            self.logger,
            "control_submitted",
            renderer_id=fingerprint(renderer.udn or renderer.location),
            action=action,
            protocol=protocol,
        )
        return {"status": "accepted", "action": action, "protocol": protocol}
