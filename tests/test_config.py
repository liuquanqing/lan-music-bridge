# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lan_music_bridge.config import ConfigError, Settings


class ConfigTests(unittest.TestCase):
    def test_example_shape_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.toml"
            config.write_text(
                """[network]
media_host = "0.0.0.0"
media_port = 49500
public_base_url = "http://192.0.2.10:49500"
admin_host = "127.0.0.1"
admin_port = 49501
[cache]
directory = "./cache"
max_bytes = 1000000
[sources]
allowed_hosts = ["media.example"]
max_download_bytes = 500000
[discovery]
timeout_seconds = 1.5
""",
                encoding="utf-8",
            )
            settings = Settings.from_file(config)
            self.assertEqual(settings.media_port, 49500)
            self.assertEqual(settings.allowed_source_hosts, ("media.example",))

    def test_admin_bind_must_be_loopback(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.toml"
            config.write_text(
                """[network]
admin_host = "0.0.0.0"
[cache]
directory = "./cache"
""",
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError):
                Settings.from_file(config)


if __name__ == "__main__":
    unittest.main()
