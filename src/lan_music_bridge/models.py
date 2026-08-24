# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ServiceEndpoint:
    service_type: str
    control_url: str
    event_url: str = ""
    scpd_url: str = ""


@dataclass(frozen=True)
class Renderer:
    location: str
    friendly_name: str
    udn: str
    services: dict[str, ServiceEndpoint] = field(default_factory=dict)

    def service(self, prefix: str) -> ServiceEndpoint | None:
        for service_type, endpoint in self.services.items():
            if service_type.startswith(prefix):
                return endpoint
        return None


@dataclass(frozen=True)
class CacheEntry:
    digest: str
    path: Path
    size: int
    content_type: str
    source_fingerprint: str
    pinned: bool = False


@dataclass(frozen=True)
class PlaybackReceipt:
    renderer_id: str
    mode: str
    media_fingerprint: str
    protocol: str
