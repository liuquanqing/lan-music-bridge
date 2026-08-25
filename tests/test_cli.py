# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

from lan_music_bridge.cli import main


class CliTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
