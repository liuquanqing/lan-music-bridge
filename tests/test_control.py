# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import threading
import unittest
from unittest import mock

from lan_music_bridge import __version__
from lan_music_bridge.control import (
    ControlError,
    RendererController,
    didl_metadata,
    soap_call,
)
from lan_music_bridge.models import Renderer, ServiceEndpoint


class ControlTests(unittest.TestCase):
    @mock.patch("lan_music_bridge.control.urllib.request.urlopen")
    def test_soap_user_agent_matches_package_version(self, urlopen):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self, _limit):
                return (
                    b'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
                    b'<s:Body><u:PlayResponse xmlns:u="urn:example"/></s:Body>'
                    b"</s:Envelope>"
                )

        urlopen.return_value = Response()
        endpoint = ServiceEndpoint("urn:example", "http://192.0.2.20/control")
        renderer = Renderer(
            "http://192.0.2.20/device.xml",
            "Example",
            "uuid:example",
            {endpoint.service_type: endpoint},
        )

        soap_call(renderer, endpoint, "Play")

        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.get_header("User-agent"),
            f"lan-music-bridge/{__version__}",
        )

    def test_metadata_is_xml_escaped(self):
        metadata = didl_metadata("A < B", "http://192.0.2.10/media/x?a=1&b=2")
        self.assertIn("A &lt; B", metadata)
        self.assertIn("a=1&amp;b=2", metadata)

    @mock.patch("lan_music_bridge.control.soap_call")
    def test_openhome_play_uses_serialized_playlist_sequence(self, call):
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
        self.assertEqual(
            [item.args[2] for item in call.call_args_list],
            ["DeleteAll", "Insert", "SeekId", "Play"],
        )

    @mock.patch("lan_music_bridge.control.soap_call")
    def test_product_source_is_selected_before_playlist_mutation(self, call):
        call.side_effect = [{}, {}, {"NewId": "7"}, {}, {}]
        product = ServiceEndpoint(
            "urn:av-openhome-org:service:Product:1",
            "http://192.0.2.20/product",
        )
        playlist = ServiceEndpoint(
            "urn:av-openhome-org:service:Playlist:1",
            "http://192.0.2.20/playlist",
        )
        renderer = Renderer(
            "http://192.0.2.20/device.xml",
            "Example",
            "uuid:example",
            {product.service_type: product, playlist.service_type: playlist},
        )

        RendererController().play(renderer, "http://192.0.2.10/media/digest")

        self.assertEqual(
            [item.args[2] for item in call.call_args_list],
            ["SetSourceBySystemName", "DeleteAll", "Insert", "SeekId", "Play"],
        )
        self.assertIs(call.call_args_list[0].args[1], product)
        self.assertEqual(call.call_args_list[0].args[3], {"Value": "Playlist"})

    @mock.patch("lan_music_bridge.control.soap_call")
    def test_source_selection_failure_leaves_playlist_untouched(self, call):
        call.side_effect = ControlError("source switch failed")
        product = ServiceEndpoint(
            "urn:av-openhome-org:service:Product:1",
            "http://192.0.2.20/product",
        )
        playlist = ServiceEndpoint(
            "urn:av-openhome-org:service:Playlist:1",
            "http://192.0.2.20/playlist",
        )
        renderer = Renderer(
            "http://192.0.2.20/device.xml",
            "Example",
            "uuid:example",
            {product.service_type: product, playlist.service_type: playlist},
        )

        with self.assertRaises(ControlError):
            RendererController().play(renderer, "http://192.0.2.10/media/digest")

        self.assertEqual(
            [item.args[2] for item in call.call_args_list],
            ["SetSourceBySystemName"],
        )

    @mock.patch("lan_music_bridge.control.soap_call")
    def test_concurrent_playlist_replacements_do_not_interleave(self, call):
        first_delete_entered = threading.Event()
        release_first = threading.Event()
        second_called = threading.Event()
        actions: list[tuple[str, str]] = []

        def fake_call(_renderer, _endpoint, action, _values=None, timeout=5.0):
            del timeout
            thread_name = threading.current_thread().name
            actions.append((thread_name, action))
            if thread_name == "first" and action == "DeleteAll":
                first_delete_entered.set()
                if not release_first.wait(2):
                    raise AssertionError("test did not release first transaction")
            if thread_name == "second":
                second_called.set()
            return {"NewId": "7"} if action == "Insert" else {}

        call.side_effect = fake_call
        playlist = ServiceEndpoint(
            "urn:av-openhome-org:service:Playlist:1",
            "http://192.0.2.20/playlist",
        )
        renderer = Renderer(
            "http://192.0.2.20/device.xml",
            "Example",
            "uuid:example",
            {playlist.service_type: playlist},
        )
        controller = RendererController()
        errors: list[BaseException] = []

        def play(name: str) -> None:
            try:
                controller.play(renderer, f"http://192.0.2.10/media/{name}")
            except BaseException as error:  # pragma: no cover - surfaced below
                errors.append(error)

        first = threading.Thread(target=play, args=("first",), name="first")
        second = threading.Thread(target=play, args=("second",), name="second")
        first.start()
        self.assertTrue(first_delete_entered.wait(2))
        second.start()
        self.assertFalse(second_called.wait(0.1))
        release_first.set()
        first.join(2)
        second.join(2)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        expected = [
            (thread_name, action)
            for thread_name in ("first", "second")
            for action in ("DeleteAll", "Insert", "SeekId", "Play")
        ]
        self.assertEqual(actions, expected)


if __name__ == "__main__":
    unittest.main()
