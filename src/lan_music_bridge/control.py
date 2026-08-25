# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import threading
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from . import __version__
from .models import PreparedTrack, Renderer, ServiceEndpoint


class ControlError(RuntimeError):
    pass


class QueueMutationError(ControlError):
    """An OpenHome queue replacement failed after device mutation began."""


class QueueUnsupportedError(ControlError):
    """The renderer has no standard multi-track queue surface."""


def _validate_control_url(url: str, renderer: Renderer) -> None:
    control = urllib.parse.urlsplit(url)
    location = urllib.parse.urlsplit(renderer.location)
    if control.scheme != "http" or not control.hostname:
        raise ControlError("renderer control URL must use HTTP")
    if control.username or control.password or control.hostname != location.hostname:
        raise ControlError("renderer control URL escaped its discovery origin")


def soap_call(
    renderer: Renderer,
    endpoint: ServiceEndpoint,
    action: str,
    values: dict[str, object] | None = None,
    timeout: float = 5.0,
) -> dict[str, str]:
    _validate_control_url(endpoint.control_url, renderer)
    fields = "".join(
        f"<{escape(str(key))}>{escape(str(value))}</{escape(str(key))}>"
        for key, value in (values or {}).items()
    )
    envelope = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        f'<s:Body><u:{action} xmlns:u="{escape(endpoint.service_type)}">'
        f"{fields}</u:{action}></s:Body></s:Envelope>"
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint.control_url,
        data=envelope,
        method="POST",
        headers={
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPACTION": f'"{endpoint.service_type}#{action}"',
            "User-Agent": f"lan-music-bridge/{__version__}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(1024 * 1024 + 1)
    except (OSError, urllib.error.HTTPError) as error:
        raise ControlError(f"renderer rejected {action}") from error
    if len(body) > 1024 * 1024:
        raise ControlError("renderer response is too large")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as error:
        raise ControlError("renderer returned invalid SOAP") from error
    fault = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Fault")
    if fault is not None:
        raise ControlError(f"renderer reported a SOAP fault for {action}")
    result: dict[str, str] = {}
    response_node = root.find(f".//{{{endpoint.service_type}}}{action}Response")
    if response_node is not None:
        for child in response_node:
            result[child.tag.rsplit("}", 1)[-1]] = child.text or ""
    return result


def didl_metadata(title: str, uri: str, content_type: str = "audio/mpeg") -> str:
    return (
        '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
        f'<item id="0" parentID="0" restricted="1"><dc:title>{escape(title)}</dc:title>'
        '<upnp:class>object.item.audioItem.musicTrack</upnp:class>'
        f'<res protocolInfo="http-get:*:{escape(content_type)}:*">{escape(uri)}</res>'
        "</item></DIDL-Lite>"
    )


class RendererController:
    def __init__(self) -> None:
        self._renderer_locks: dict[str, threading.RLock] = {}
        self._renderer_locks_guard = threading.Lock()

    def _renderer_lock(self, renderer: Renderer) -> threading.RLock:
        key = renderer.udn or renderer.location
        with self._renderer_locks_guard:
            return self._renderer_locks.setdefault(key, threading.RLock())

    def play(
        self,
        renderer: Renderer,
        uri: str,
        title: str = "LAN media",
        content_type: str = "audio/mpeg",
    ) -> str:
        with self._renderer_lock(renderer):
            return self._play_locked(renderer, uri, title, content_type)

    def replace_queue(
        self,
        renderer: Renderer,
        tracks: tuple[PreparedTrack, ...],
    ) -> str:
        if not tracks:
            raise ValueError("queue must contain at least one item")
        with self._renderer_lock(renderer):
            return self._replace_queue_locked(renderer, tracks)

    def _replace_queue_locked(
        self,
        renderer: Renderer,
        tracks: tuple[PreparedTrack, ...],
    ) -> str:
        playlist = renderer.service("urn:av-openhome-org:service:Playlist:")
        if not playlist:
            raise QueueUnsupportedError(
                "multi-track queues require an OpenHome Playlist service"
            )
        product = renderer.service("urn:av-openhome-org:service:Product:")
        if product:
            # Source selection happens before queue mutation. A failure here leaves
            # the existing Playlist entries untouched.
            soap_call(
                renderer,
                product,
                "SetSourceBySystemName",
                {"Value": "Playlist"},
            )
        try:
            soap_call(renderer, playlist, "DeleteAll")
            after_id: int | str = 0
            first_id = ""
            for track in tracks:
                result = soap_call(
                    renderer,
                    playlist,
                    "Insert",
                    {
                        "AfterId": after_id,
                        "Uri": track.uri,
                        "Metadata": didl_metadata(
                            track.title, track.uri, track.content_type
                        ),
                    },
                )
                item_id = result.get("NewId", "")
                if not item_id:
                    raise ControlError("OpenHome Insert returned no NewId")
                if not first_id:
                    first_id = item_id
                after_id = item_id
            soap_call(renderer, playlist, "SeekId", {"Value": first_id})
            soap_call(renderer, playlist, "Play")
        except Exception as error:
            raise QueueMutationError(
                "OpenHome queue replacement may be partially applied"
            ) from error
        return "openhome-playlist"

    def _play_locked(
        self,
        renderer: Renderer,
        uri: str,
        title: str,
        content_type: str,
    ) -> str:
        metadata = didl_metadata(title, uri, content_type)
        playlist = renderer.service("urn:av-openhome-org:service:Playlist:")
        if playlist:
            product = renderer.service("urn:av-openhome-org:service:Product:")
            if product:
                # Playlist state can remain readable while another Product source is
                # active. Select Playlist before mutation so a failed source switch
                # leaves the prior queue untouched.
                soap_call(
                    renderer,
                    product,
                    "SetSourceBySystemName",
                    {"Value": "Playlist"},
                )
            soap_call(renderer, playlist, "DeleteAll")
            result = soap_call(
                renderer,
                playlist,
                "Insert",
                {"AfterId": 0, "Uri": uri, "Metadata": metadata},
            )
            item_id = result.get("NewId", "")
            if item_id:
                soap_call(renderer, playlist, "SeekId", {"Value": item_id})
            soap_call(renderer, playlist, "Play")
            return "openhome-playlist"
        av_transport = renderer.service("urn:schemas-upnp-org:service:AVTransport:")
        if av_transport:
            soap_call(
                renderer,
                av_transport,
                "SetAVTransportURI",
                {"InstanceID": 0, "CurrentURI": uri, "CurrentURIMetaData": metadata},
            )
            soap_call(renderer, av_transport, "Play", {"InstanceID": 0, "Speed": 1})
            return "upnp-avtransport"
        raise ControlError("renderer exposes neither OpenHome Playlist nor UPnP AVTransport")

    def command(self, renderer: Renderer, action: str) -> str:
        with self._renderer_lock(renderer):
            return self._command_locked(renderer, action)

    def _command_locked(self, renderer: Renderer, action: str) -> str:
        normalized = action.lower()
        if normalized not in {"play", "pause", "stop"}:
            raise ControlError("unsupported command")
        playlist = renderer.service("urn:av-openhome-org:service:Playlist:")
        if playlist:
            soap_call(renderer, playlist, normalized.capitalize())
            return "openhome-playlist"
        av_transport = renderer.service("urn:schemas-upnp-org:service:AVTransport:")
        if av_transport:
            values = {"InstanceID": 0}
            if normalized == "play":
                values["Speed"] = 1
            soap_call(renderer, av_transport, normalized.capitalize(), values)
            return "upnp-avtransport"
        raise ControlError("renderer exposes no supported transport service")
