# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import unittest

from lan_music_bridge.discovery import parse_device_description, parse_ssdp_headers


DEVICE = b"""<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
  <device>
    <deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType>
    <friendlyName>Example Renderer</friendlyName>
    <UDN>uuid:example-renderer</UDN>
    <serviceList>
      <service>
        <serviceType>urn:av-openhome-org:service:Playlist:1</serviceType>
        <serviceId>urn:av-openhome-org:serviceId:Playlist</serviceId>
        <controlURL>/oh/playlist</controlURL>
        <eventSubURL>/oh/playlist/event</eventSubURL>
        <SCPDURL>/oh/playlist.xml</SCPDURL>
      </service>
    </serviceList>
  </device>
</root>"""


class DiscoveryTests(unittest.TestCase):
    def test_ssdp_headers_are_case_insensitive(self):
        headers = parse_ssdp_headers(
            b"HTTP/1.1 200 OK\r\nLOCATION: http://192.0.2.20/device.xml\r\nST: x\r\n\r\n"
        )
        self.assertEqual(headers["location"], "http://192.0.2.20/device.xml")

    def test_device_description_resolves_service_urls(self):
        renderer = parse_device_description("http://192.0.2.20/device.xml", DEVICE)
        self.assertEqual(renderer.friendly_name, "Example Renderer")
        playlist = renderer.service("urn:av-openhome-org:service:Playlist:")
        self.assertIsNotNone(playlist)
        self.assertEqual(playlist.control_url, "http://192.0.2.20/oh/playlist")


if __name__ == "__main__":
    unittest.main()
