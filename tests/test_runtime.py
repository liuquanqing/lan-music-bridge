# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from lan_music_bridge.models import CacheEntry, Renderer
from lan_music_bridge.runtime import BridgeRuntime, RendererIntentSuperseded

from .helpers import settings_for


class _BlockingPublisher:
    def __init__(self, first_digest: str):
        self.first_digest = first_digest
        self.first_entered = threading.Event()
        self.release_first = threading.Event()

    def publish(self, entry: CacheEntry) -> str:
        if entry.digest == self.first_digest:
            self.first_entered.set()
            if not self.release_first.wait(2):
                raise AssertionError("test did not release the first preparation")
        return f"http://192.0.2.20/media/{entry.digest}"


class _RecordingController:
    def __init__(self):
        self.played: list[str] = []
        self.commands: list[str] = []

    def play(
        self,
        _renderer: Renderer,
        uri: str,
        title: str = "LAN media",
        content_type: str = "audio/mpeg",
    ) -> str:
        del title, content_type
        self.played.append(uri)
        return "test-protocol"

    def command(self, _renderer: Renderer, action: str) -> str:
        self.commands.append(action)
        return "test-protocol"


class RuntimeIntentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.first = self.root / "first.flac"
        self.second = self.root / "second.flac"
        self.first.write_bytes(b"first")
        self.second.write_bytes(b"second")
        self.runtime = BridgeRuntime(settings_for(self.root))
        self.renderer = Renderer(
            "http://192.0.2.20/device.xml",
            "Example",
            "uuid:example",
            {},
        )
        self.runtime.renderers = [self.renderer]
        first_entry = self.runtime.cache.ingest_file(self.first, "audio/flac")
        self.publisher = _BlockingPublisher(first_entry.digest)
        self.controller = _RecordingController()
        self.runtime.publisher = self.publisher
        self.runtime.controller = self.controller

    def tearDown(self):
        self.publisher.release_first.set()
        self.temporary.cleanup()

    def _start_first_play(self) -> tuple[threading.Thread, list[BaseException]]:
        errors: list[BaseException] = []

        def play() -> None:
            try:
                self.runtime.play("uuid:example", "local", str(self.first))
            except BaseException as error:  # pragma: no cover - asserted below
                errors.append(error)

        thread = threading.Thread(target=play)
        thread.start()
        self.assertTrue(self.publisher.first_entered.wait(2))
        return thread, errors

    def test_latest_play_wins_when_older_preparation_finishes_last(self):
        first_thread, errors = self._start_first_play()

        receipt = self.runtime.play("uuid:example", "local", str(self.second))
        self.publisher.release_first.set()
        first_thread.join(2)

        self.assertFalse(first_thread.is_alive())
        self.assertEqual(receipt["protocol"], "test-protocol")
        self.assertEqual(len(self.controller.played), 1)
        second_digest = self.runtime.cache.ingest_file(self.second).digest
        self.assertIn(second_digest, self.controller.played[0])
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RendererIntentSuperseded)

    def test_control_command_supersedes_pending_play(self):
        first_thread, errors = self._start_first_play()

        receipt = self.runtime.command("uuid:example", "stop")
        self.publisher.release_first.set()
        first_thread.join(2)

        self.assertFalse(first_thread.is_alive())
        self.assertEqual(receipt["status"], "accepted")
        self.assertEqual(self.controller.commands, ["stop"])
        self.assertEqual(self.controller.played, [])
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RendererIntentSuperseded)


if __name__ == "__main__":
    unittest.main()
