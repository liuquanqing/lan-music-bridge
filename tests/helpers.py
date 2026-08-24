# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

from lan_music_bridge.config import Settings


def settings_for(root: Path, **overrides) -> Settings:  # noqa: ANN003
    values = {
        "media_host": "127.0.0.1",
        "media_port": 49500,
        "public_base_url": "http://192.0.2.10:49500",
        "admin_host": "127.0.0.1",
        "admin_port": 49501,
        "cache_dir": root / "cache",
        "cache_max_bytes": 16 * 1024 * 1024,
        "source_max_bytes": 4 * 1024 * 1024,
        "allowed_source_hosts": ("media.example",),
        "allow_private_sources": False,
        "discovery_source_ip": "0.0.0.0",
        "discovery_timeout": 0.1,
        "publisher_factory": "",
    }
    values.update(overrides)
    return Settings(**values)
