# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import ipaddress
import socket
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .models import Renderer, ServiceEndpoint

SSDP_ADDRESS = ("239.255.255.250", 1900)
SEARCH_TARGETS = (
    "urn:schemas-upnp-org:device:MediaRenderer:1",
    "urn:av-openhome-org:device:Source:1",
)


def parse_ssdp_headers(payload: bytes) -> dict[str, str]:
    text = payload.decode("iso-8859-1", "replace")
    lines = text.replace("\r\n", "\n").split("\n")
    result: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip().lower()] = value.strip()
    return result


def _safe_location(location: str, responder_ip: str) -> str:
    parsed = urllib.parse.urlsplit(location)
    if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("discovery location must be credential-free HTTP")
    addresses = {
        record[4][0]
        for record in socket.getaddrinfo(parsed.hostname, parsed.port or 80, type=socket.SOCK_STREAM)
    }
    responder = ipaddress.ip_address(responder_ip)
    if not any(ipaddress.ip_address(raw) == responder for raw in addresses):
        raise ValueError("discovery location host does not match responder")
    return location


def parse_device_description(location: str, body: bytes) -> Renderer:
    if len(body) > 1024 * 1024:
        raise ValueError("device description is too large")
    root = ET.fromstring(body)
    device = root.find(".//{*}device")
    if device is None:
        raise ValueError("device description has no device")

    def text(name: str) -> str:
        node = device.find(f"{{*}}{name}")
        return (node.text or "").strip() if node is not None else ""

    services: dict[str, ServiceEndpoint] = {}
    for service in device.findall(".//{*}service"):
        service_type = (service.findtext("{*}serviceType") or "").strip()
        control = (service.findtext("{*}controlURL") or "").strip()
        if not service_type or not control:
            continue
        services[service_type] = ServiceEndpoint(
            service_type=service_type,
            control_url=urllib.parse.urljoin(location, control),
            event_url=urllib.parse.urljoin(
                location, (service.findtext("{*}eventSubURL") or "").strip()
            ),
            scpd_url=urllib.parse.urljoin(
                location, (service.findtext("{*}SCPDURL") or "").strip()
            ),
        )
    return Renderer(
        location=location,
        friendly_name=text("friendlyName") or "Unnamed renderer",
        udn=text("UDN"),
        services=services,
    )


class SsdpDiscovery:
    def __init__(self, source_ip: str = "0.0.0.0"):
        self.source_ip = source_ip

    def discover(self, timeout: float = 2.0) -> list[Renderer]:
        responses: dict[str, tuple[str, str]] = {}
        for target in SEARCH_TARGETS:
            request = (
                "M-SEARCH * HTTP/1.1\r\n"
                f"HOST: {SSDP_ADDRESS[0]}:{SSDP_ADDRESS[1]}\r\n"
                'MAN: "ssdp:discover"\r\n'
                "MX: 1\r\n"
                f"ST: {target}\r\n\r\n"
            ).encode("ascii")
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
                sock.settimeout(timeout)
                sock.bind((self.source_ip, 0))
                sock.sendto(request, SSDP_ADDRESS)
                while True:
                    try:
                        payload, peer = sock.recvfrom(65535)
                    except TimeoutError:
                        break
                    headers = parse_ssdp_headers(payload)
                    location = headers.get("location", "")
                    if location:
                        responses[location] = (location, peer[0])
        renderers: list[Renderer] = []
        for location, peer_ip in responses.values():
            try:
                safe_location = _safe_location(location, peer_ip)
                request = urllib.request.Request(
                    safe_location, headers={"User-Agent": "lan-music-bridge/0.1"}
                )
                with urllib.request.urlopen(request, timeout=3) as response:
                    body = response.read(1024 * 1024 + 1)
                renderer = parse_device_description(safe_location, body)
                if renderer.service("urn:av-openhome-org:service:") or renderer.service(
                    "urn:schemas-upnp-org:service:AVTransport:"
                ):
                    renderers.append(renderer)
            except (OSError, ValueError, ET.ParseError):
                continue
        return sorted(renderers, key=lambda item: (item.friendly_name, item.udn))
