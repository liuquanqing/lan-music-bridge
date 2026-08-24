# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from lan_music_bridge.http_server import BridgeHTTPServer, MediaHandler, parse_byte_range
from lan_music_bridge.runtime import BridgeRuntime

from .helpers import settings_for


class RangeTests(unittest.TestCase):
    def test_explicit_and_suffix_ranges(self):
        self.assertEqual(parse_byte_range("bytes=2-5", 10), (2, 5, True))
        self.assertEqual(parse_byte_range("bytes=-3", 10), (7, 9, True))
        with self.assertRaises(ValueError):
            parse_byte_range("bytes=20-30", 10)


class MediaServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        settings = settings_for(root, media_port=0, admin_port=0)
        self.runtime = BridgeRuntime(settings)
        self.server = BridgeHTTPServer(("127.0.0.1", 0), MediaHandler, self.runtime)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temporary.cleanup()

    def test_health_is_minimal_and_redacted(self):
        self.runtime.sources.register("https://media.example/item?token=hidden")
        with urllib.request.urlopen(f"{self.base}/health") as response:
            health = json.load(response)
        rendered = json.dumps(health)
        self.assertEqual(health["status"], "ok")
        self.assertNotIn("hidden", rendered)
        self.assertNotIn("media.example", rendered)

    def test_cached_media_supports_range(self):
        source = Path(self.temporary.name) / "track.bin"
        source.write_bytes(b"0123456789")
        entry = self.runtime.cache.ingest_file(source, "audio/flac")
        request = urllib.request.Request(
            f"{self.base}/media/{entry.digest}", headers={"Range": "bytes=2-5"}
        )
        with urllib.request.urlopen(request) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.read(), b"2345")

    def test_access_log_redacts_stream_token(self):
        token = "super-secret-stream-token"
        with self.assertLogs("lan_music_bridge.http", level="INFO") as capture:
            try:
                urllib.request.urlopen(f"{self.base}/stream/{token}")
            except urllib.error.HTTPError as error:
                error.close()
        rendered = "\n".join(capture.output)
        self.assertNotIn(token, rendered)
        self.assertIn("/stream/<redacted>", rendered)


if __name__ == "__main__":
    unittest.main()
