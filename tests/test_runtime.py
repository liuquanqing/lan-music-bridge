# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from lan_music_bridge.models import CacheEntry, PreparedTrack, Renderer, ServiceEndpoint
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
        self.queues: list[tuple[PreparedTrack, ...]] = []
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

    def replace_queue(
        self, _renderer: Renderer, tracks: tuple[PreparedTrack, ...]
    ) -> str:
        self.queues.append(tracks)
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
            {
                "urn:av-openhome-org:service:Playlist:1": ServiceEndpoint(
                    "urn:av-openhome-org:service:Playlist:1",
                    "http://192.0.2.20/playlist",
                )
            },
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

    def test_latest_queue_wins_and_superseded_stream_token_is_discarded(self):
        errors: list[BaseException] = []

        def submit_first() -> None:
            try:
                self.runtime.queue(
                    "uuid:example",
                    [
                        {
                            "mode": "stream",
                            "source": "https://media.example/temporary",
                            "title": "Temporary",
                        },
                        {
                            "mode": "local",
                            "source": str(self.first),
                            "title": "First",
                        },
                    ],
                )
            except BaseException as error:  # pragma: no cover - asserted below
                errors.append(error)

        with mock.patch("lan_music_bridge.runtime.validate_source_url"):
            first_thread = threading.Thread(target=submit_first)
            first_thread.start()
            self.assertTrue(self.publisher.first_entered.wait(2))
            receipt = self.runtime.queue(
                "uuid:example",
                [
                    {
                        "mode": "local",
                        "source": str(self.second),
                        "title": "Second",
                    }
                ],
            )
            self.publisher.release_first.set()
            first_thread.join(2)

        self.assertFalse(first_thread.is_alive())
        self.assertEqual(receipt["item_count"], 1)
        self.assertEqual(len(self.controller.queues), 1)
        self.assertEqual(self.controller.queues[0][0].title, "Second")
        self.assertEqual(self.runtime.sources.count(), 0)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RendererIntentSuperseded)

    def test_preparation_failure_does_not_mutate_queue_and_discards_tokens(self):
        missing = self.root / "missing.flac"
        with (
            mock.patch("lan_music_bridge.runtime.validate_source_url"),
            self.assertRaises(FileNotFoundError),
        ):
            self.runtime.queue(
                "uuid:example",
                [
                    {
                        "mode": "stream",
                        "source": "https://media.example/temporary",
                    },
                    {"mode": "local", "source": str(missing)},
                ],
            )

        self.assertEqual(self.controller.queues, [])
        self.assertEqual(self.runtime.sources.count(), 0)

    def test_queue_logs_do_not_expose_source_urls_or_titles(self):
        source = "https://media.example/private?signature=hidden"
        title = "private listening title"
        with (
            mock.patch("lan_music_bridge.runtime.validate_source_url"),
            self.assertLogs("lan_music_bridge", level="INFO") as capture,
        ):
            receipt = self.runtime.queue(
                "uuid:example",
                [{"mode": "stream", "source": source, "title": title}],
            )

        rendered = "\n".join(capture.output)
        self.assertEqual(receipt["item_count"], 1)
        self.assertNotIn(source, rendered)
        self.assertNotIn(title, rendered)
        self.assertNotIn("hidden", rendered)
        self.assertEqual(self.controller.queues[0][0].content_type, "audio/mpeg")

    def test_avtransport_rejection_happens_before_source_validation(self):
        self.runtime.renderers = [
            Renderer(
                "http://192.0.2.20/device.xml",
                "Example",
                "uuid:example",
                {
                    "urn:schemas-upnp-org:service:AVTransport:1": ServiceEndpoint(
                        "urn:schemas-upnp-org:service:AVTransport:1",
                        "http://192.0.2.20/transport",
                    )
                },
            )
        ]
        with (
            mock.patch("lan_music_bridge.runtime.validate_source_url") as validate,
            self.assertRaisesRegex(RuntimeError, "OpenHome Playlist"),
        ):
            self.runtime.queue(
                "uuid:example",
                [{"mode": "stream", "source": "https://media.example/item"}],
            )

        validate.assert_not_called()
        self.assertEqual(self.runtime.sources.count(), 0)
        self.assertEqual(self.controller.queues, [])


if __name__ == "__main__":
    unittest.main()
