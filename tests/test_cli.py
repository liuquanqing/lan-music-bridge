# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import io
import json
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from lan_music_bridge.cli import admin_request, main


class CliTests(unittest.TestCase):
    def test_admin_request_surfaces_safe_server_error(self):
        error = urllib.error.HTTPError(
            "http://127.0.0.1:49501/v1/queue",
            422,
            "Unprocessable Entity",
            {},
            io.BytesIO(b'{"error":"multi-track queue requires OpenHome Playlist"}'),
        )
        settings = SimpleNamespace(admin_host="127.0.0.1", admin_port=49501)
        with (
            mock.patch("lan_music_bridge.cli.urllib.request.urlopen", side_effect=error),
            self.assertRaisesRegex(SystemExit, "requires OpenHome Playlist"),
        ):
            admin_request(settings, "/v1/queue", {"items": []})

    def test_play_passes_explicit_content_type_to_admin_api(self):
        with (
            mock.patch("lan_music_bridge.cli.Settings.from_file", return_value=object()),
            mock.patch(
                "lan_music_bridge.cli.admin_request", return_value={"status": "accepted"}
            ) as request,
            redirect_stdout(io.StringIO()),
        ):
            result = main(
                [
                    "--config",
                    "config.toml",
                    "play",
                    "--renderer",
                    "uuid:example",
                    "--mode",
                    "local",
                    "--file",
                    "track.flac",
                    "--content-type",
                    "audio/flac",
                ]
            )

        self.assertEqual(result, 0)
        self.assertEqual(request.call_args.args[2]["content_type"], "audio/flac")

    def test_queue_posts_ordered_playlist_and_resolves_relative_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            playlist = root / "playlist.json"
            playlist.write_text(
                json.dumps(
                    [
                        {
                            "mode": "local",
                            "source": "first.flac",
                            "title": "First",
                            "content_type": "audio/flac",
                        },
                        {
                            "mode": "stream",
                            "source": "https://media.example/second",
                            "title": "Second",
                        },
                    ]
                ),
                encoding="utf-8",
            )
            with (
                mock.patch(
                    "lan_music_bridge.cli.Settings.from_file", return_value=object()
                ),
                mock.patch(
                    "lan_music_bridge.cli.admin_request",
                    return_value={"status": "accepted"},
                ) as request,
                redirect_stdout(io.StringIO()),
            ):
                result = main(
                    [
                        "--config",
                        "config.toml",
                        "queue",
                        "--renderer",
                        "uuid:example",
                        "--playlist",
                        str(playlist),
                    ]
                )

        self.assertEqual(result, 0)
        self.assertEqual(request.call_args.args[1], "/v1/queue")
        items = request.call_args.args[2]["items"]
        self.assertEqual([item["title"] for item in items], ["First", "Second"])
        self.assertEqual(items[0]["source"], str((root / "first.flac").resolve()))
        self.assertEqual(items[1]["source"], "https://media.example/second")


if __name__ == "__main__":
    unittest.main()
