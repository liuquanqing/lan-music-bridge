# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import http.server
import tempfile
import threading
import unittest
from pathlib import Path

from lan_music_bridge.net import open_source

from .helpers import settings_for


class SourceHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/media")
            self.end_headers()
            return
        body = b"media-bytes"
        self.send_response(200)
        self.send_header("Content-Type", "audio/flac")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        return


class PinnedNetworkTests(unittest.TestCase):
    def setUp(self):
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SourceHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_explicitly_allowed_private_source_can_be_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = settings_for(
                Path(tmp),
                allowed_source_hosts=("127.0.0.1",),
                allow_private_sources=True,
            )
            url = f"http://127.0.0.1:{self.server.server_address[1]}/media"
            with open_source(url, settings) as response:
                self.assertEqual(response.read(), b"media-bytes")

    def test_redirect_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = settings_for(
                Path(tmp),
                allowed_source_hosts=("127.0.0.1",),
                allow_private_sources=True,
            )
            url = f"http://127.0.0.1:{self.server.server_address[1]}/redirect"
            with self.assertRaises(OSError):
                with open_source(url, settings):
                    pass


if __name__ == "__main__":
    unittest.main()
