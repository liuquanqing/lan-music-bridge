# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lan_music_bridge.security import log_event, redact_value, validate_source_url

from .helpers import settings_for


class SecurityTests(unittest.TestCase):
    def test_recursive_redaction_removes_urls_and_secret_fields(self):
        result = redact_value(
            {"source_url": "https://media.example/item?token=hidden", "nested": {"cookie": "hidden"}}
        )
        rendered = repr(result)
        self.assertNotIn("hidden", rendered)
        self.assertNotIn("media.example", rendered)

    @mock.patch("lan_music_bridge.net.socket.getaddrinfo")
    def test_source_url_requires_allowlist_and_public_resolution(self, resolve):
        resolve.return_value = [(2, 1, 6, "", ("8.8.8.8", 443))]
        with tempfile.TemporaryDirectory() as tmp:
            settings = settings_for(Path(tmp))
            self.assertEqual(
                validate_source_url("https://media.example/audio.flac", settings),
                "https://media.example/audio.flac",
            )
            with self.assertRaises(ValueError):
                validate_source_url("https://other.example/audio.flac", settings)

    @mock.patch("lan_music_bridge.net.socket.getaddrinfo")
    def test_private_resolution_is_rejected_by_default(self, resolve):
        resolve.return_value = [(10, 1, 6, "", ("::1", 80, 0, 0))]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                validate_source_url(
                    "http://media.example/audio.flac", settings_for(Path(tmp))
                )

    def test_structured_log_does_not_emit_signed_url(self):
        logger = logging.getLogger("test-redaction")
        with self.assertLogs(logger, level="INFO") as capture:
            log_event(
                logger,
                "test",
                url="https://media.example/item?signature=hidden",
            )
        rendered = "\n".join(capture.output)
        self.assertNotIn("hidden", rendered)
        self.assertNotIn("media.example", rendered)


if __name__ == "__main__":
    unittest.main()
