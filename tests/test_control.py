# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import unittest
from unittest import mock

from lan_music_bridge.control import RendererController, didl_metadata
from lan_music_bridge.models import Renderer, ServiceEndpoint


class ControlTests(unittest.TestCase):
    def test_metadata_is_xml_escaped(self):
        metadata = didl_metadata("A < B", "http://192.0.2.10/media/x?a=1&b=2")
        self.assertIn("A &lt; B", metadata)
        self.assertIn("a=1&amp;b=2", metadata)

    @mock.patch("lan_music_bridge.control.soap_call")
    def test_openhome_play_uses_atomic_playlist_sequence(self, call):
        call.side_effect = [{}, {"NewId": "7"}, {}, {}]
        endpoint = ServiceEndpoint(
            "urn:av-openhome-org:service:Playlist:1",
            "http://192.0.2.20/playlist",
        )
        renderer = Renderer(
            "http://192.0.2.20/device.xml",
            "Example",
            "uuid:example",
            {endpoint.service_type: endpoint},
        )
        protocol = RendererController().play(
            renderer, "http://192.0.2.10/media/digest", "Track"
        )
        self.assertEqual(protocol, "openhome-playlist")
        self.assertEqual([item.args[2] for item in call.call_args_list], ["DeleteAll", "Insert", "SeekId", "Play"])


if __name__ == "__main__":
    unittest.main()
