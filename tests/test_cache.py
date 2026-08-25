# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import io
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest import mock

from lan_music_bridge.cache import CacheStore

from .helpers import settings_for


class CacheTests(unittest.TestCase):
    def test_local_ingest_is_content_addressed_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "track.flac"
            source.write_bytes(b"fLaC" + b"audio" * 20)
            cache = CacheStore(settings_for(root))
            first = cache.ingest_file(source, "audio/flac")
            second = cache.ingest_file(source, "audio/flac")
            self.assertEqual(first.digest, second.digest)
            self.assertEqual(cache.stats()["entries"], 1)
            self.assertEqual(first.path.read_bytes(), source.read_bytes())

    def test_pinned_entry_survives_quota_eviction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = CacheStore(settings_for(root, cache_max_bytes=10))
            first_file = root / "first.bin"
            first_file.write_bytes(b"a" * 8)
            first = cache.ingest_file(first_file)
            cache.pin(first.digest)
            second_file = root / "second.bin"
            second_file.write_bytes(b"b" * 8)
            with self.assertRaisesRegex(ValueError, "cache quota"):
                cache.ingest_file(second_file)
            self.assertEqual(cache.get(first.digest).digest, first.digest)

    def test_truncated_http_response_is_not_published(self):
        class Response(io.BytesIO):
            def __init__(self, body: bytes, declared_length: int):
                super().__init__(body)
                self.headers = Message()
                self.headers["Content-Length"] = str(declared_length)
                self.headers["Content-Type"] = "audio/flac"

            def __enter__(self):
                return self

            def __exit__(self, _type, _value, _traceback):
                self.close()

        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheStore(settings_for(Path(tmp)))
            response = Response(b"partial-audio", declared_length=100)
            with mock.patch("lan_music_bridge.cache.open_source", return_value=response):
                with self.assertRaisesRegex(ValueError, "does not match Content-Length"):
                    cache.ingest_url("https://media.example/track.flac")
            self.assertEqual(cache.stats(), {"entries": 0, "bytes": 0})
            self.assertEqual(list(cache.blobs.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
