# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

from lan_music_bridge import __version__
from lan_music_bridge.http_server import BaseHandler


class VersionTests(unittest.TestCase):
    def test_version_is_semantic_and_shared_with_http_server(self):
        self.assertRegex(__version__, re.compile(r"^\d+\.\d+\.\d+$"))
        self.assertEqual(BaseHandler.server_version, f"lan-music-bridge/{__version__}")

    def test_packaging_uses_package_version_as_single_source(self):
        project_root = Path(__file__).resolve().parents[1]
        data = tomllib.loads((project_root / "pyproject.toml").read_text())
        self.assertNotIn("version", data["project"])
        self.assertIn("version", data["project"]["dynamic"])
        self.assertEqual(
            data["tool"]["setuptools"]["dynamic"]["version"]["attr"],
            "lan_music_bridge.__version__",
        )


if __name__ == "__main__":
    unittest.main()
