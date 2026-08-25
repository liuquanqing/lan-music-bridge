# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from lan_music_bridge.control import QueueMutationError
from lan_music_bridge.http_server import (
    AdminHandler,
    BridgeHTTPServer,
    MediaHandler,
    parse_byte_range,
)
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
        self.assertNotIn("127.0.0.1", rendered)
        self.assertIn("peer_fingerprint", rendered)
        self.assertIn("/stream/<redacted>", rendered)


class AdminServerTests(unittest.TestCase):
    def test_queue_route_passes_ordered_items_to_runtime(self):
        class Runtime:
            def __init__(self):
                self.received = None

            def queue(self, selector, items):  # noqa: ANN001
                self.received = (selector, items)
                return {"status": "accepted", "item_count": len(items)}

        runtime = Runtime()
        server = BridgeHTTPServer(("127.0.0.1", 0), AdminHandler, runtime)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        payload = {
            "renderer": "uuid:example",
            "items": [
                {"mode": "local", "source": "/srv/music/first.flac"},
                {"mode": "local", "source": "/srv/music/second.flac"},
            ],
        }
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_address[1]}/v1/queue",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request) as response:
                result = json.load(response)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)

        self.assertEqual(result["item_count"], 2)
        self.assertEqual(runtime.received, ("uuid:example", payload["items"]))

    def test_queue_mutation_failure_reports_possible_partial_state(self):
        class Runtime:
            def queue(self, selector, items):  # noqa: ANN001
                del selector, items
                raise QueueMutationError("details stay out of the response")

        server = BridgeHTTPServer(("127.0.0.1", 0), AdminHandler, Runtime())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_address[1]}/v1/queue",
            data=json.dumps(
                {
                    "renderer": "uuid:example",
                    "items": [{"mode": "local", "source": "/srv/music/a.flac"}],
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            try:
                urllib.request.urlopen(request)
            except urllib.error.HTTPError as error:
                status = error.code
                result = json.load(error)
                error.close()
            else:  # pragma: no cover - failure path asserted below
                self.fail("queue mutation failure returned success")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)

        self.assertEqual(status, 409)
        self.assertEqual(result["device_queue_may_be_partial"], True)
        self.assertNotIn("details", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
