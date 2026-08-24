# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
