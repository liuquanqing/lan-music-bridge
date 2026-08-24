# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import ipaddress
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    media_host: str
    media_port: int
    public_base_url: str
    admin_host: str
    admin_port: int
    cache_dir: Path
    cache_max_bytes: int
    source_max_bytes: int
    allowed_source_hosts: tuple[str, ...]
    allow_private_sources: bool
    discovery_source_ip: str
    discovery_timeout: float
    publisher_factory: str

    @classmethod
    def from_file(cls, path: str | Path) -> "Settings":
        config_path = Path(path)
        with config_path.open("rb") as source:
            raw = tomllib.load(source)
        network = raw.get("network", {})
        cache = raw.get("cache", {})
        sources = raw.get("sources", {})
        discovery = raw.get("discovery", {})
        publisher = raw.get("publisher", {})
        settings = cls(
            media_host=str(network.get("media_host", "0.0.0.0")),
            media_port=int(network.get("media_port", 49500)),
            public_base_url=str(network.get("public_base_url", "")),
            admin_host=str(network.get("admin_host", "127.0.0.1")),
            admin_port=int(network.get("admin_port", 49501)),
            cache_dir=Path(cache.get("directory", "./var/cache")).expanduser(),
            cache_max_bytes=int(cache.get("max_bytes", 10 * 1024**3)),
            source_max_bytes=int(sources.get("max_download_bytes", 2 * 1024**3)),
            allowed_source_hosts=tuple(
                str(item).lower().rstrip(".")
                for item in sources.get("allowed_hosts", [])
            ),
            allow_private_sources=bool(sources.get("allow_private", False)),
            discovery_source_ip=str(discovery.get("source_ip", "0.0.0.0")),
            discovery_timeout=float(discovery.get("timeout_seconds", 2.0)),
            publisher_factory=str(publisher.get("factory", "")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not 1 <= self.media_port <= 65535 or not 1 <= self.admin_port <= 65535:
            raise ConfigError("ports must be between 1 and 65535")
        try:
            admin_ip = ipaddress.ip_address(self.admin_host)
        except ValueError as error:
            raise ConfigError("admin_host must be a loopback IP literal") from error
        if not admin_ip.is_loopback:
            raise ConfigError("admin API must bind to loopback")
        if self.cache_max_bytes <= 0 or self.source_max_bytes <= 0:
            raise ConfigError("cache and source limits must be positive")
        if self.discovery_timeout <= 0 or self.discovery_timeout > 30:
            raise ConfigError("discovery timeout must be in (0, 30]")
        if self.public_base_url:
            parsed = urlsplit(self.public_base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ConfigError("public_base_url must be an HTTP(S) origin")
            if (
                parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
            ):
                raise ConfigError("public_base_url must be an origin without path, credentials, query, or fragment")
        for host in self.allowed_source_hosts:
            if not host or "/" in host or ":" in host:
                raise ConfigError("allowed source hosts must be bare DNS names or IP literals")
