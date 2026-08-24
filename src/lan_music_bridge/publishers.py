# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib
from typing import Protocol

from .cache import CacheStore
from .config import Settings
from .models import CacheEntry


class LocalPublisher(Protocol):
    def publish(self, entry: CacheEntry) -> str: ...


class BridgeHttpPublisher:
    def __init__(self, settings: Settings):
        self.base_url = settings.public_base_url.rstrip("/")

    def publish(self, entry: CacheEntry) -> str:
        if not self.base_url:
            raise ValueError("public_base_url is required for bridge-hosted media")
        return f"{self.base_url}/media/{entry.digest}"


def load_publisher(settings: Settings, cache: CacheStore) -> LocalPublisher:
    if not settings.publisher_factory:
        return BridgeHttpPublisher(settings)
    if ":" not in settings.publisher_factory:
        raise ValueError("publisher factory must use module:callable syntax")
    module_name, callable_name = settings.publisher_factory.split(":", 1)
    factory = getattr(importlib.import_module(module_name), callable_name)
    publisher = factory(settings=settings, cache=cache)
    if not callable(getattr(publisher, "publish", None)):
        raise TypeError("publisher factory did not return a publish-capable adapter")
    return publisher
