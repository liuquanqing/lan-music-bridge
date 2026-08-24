# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from .config import Settings


@dataclass(frozen=True)
class ResolvedSource:
    scheme: str
    host: str
    port: int
    path: str
    addresses: tuple[str, ...]


def resolve_source(url: str, settings: Settings) -> ResolvedSource:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("source URL must use HTTP or HTTPS")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("source URL must not contain credentials")
    host = parsed.hostname.lower().rstrip(".")
    if host not in settings.allowed_source_hosts:
        raise ValueError("source host is not allow-listed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise ValueError("source host does not resolve") from error
    addresses = tuple(sorted({record[4][0] for record in records}))
    if not addresses:
        raise ValueError("source host has no address")
    for raw in addresses:
        address = ipaddress.ip_address(raw)
        unsafe = (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        )
        if unsafe and not settings.allow_private_sources:
            raise ValueError("source host resolves to a non-public address")
    path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    return ResolvedSource(parsed.scheme, host, port, path, addresses)


def _host_header(target: ResolvedSource) -> str:
    host = f"[{target.host}]" if ":" in target.host else target.host
    default_port = 443 if target.scheme == "https" else 80
    return host if target.port == default_port else f"{host}:{target.port}"


@contextmanager
def open_source(
    url: str,
    settings: Settings,
    headers: dict[str, str] | None = None,
    timeout: float = 20,
):
    """Open one validated source without a second DNS lookup or redirects."""
    target = resolve_source(url, settings)
    last_error: OSError | None = None
    connection: http.client.HTTPConnection | None = None
    for address in target.addresses:
        try:
            raw_socket = socket.create_connection((address, target.port), timeout=timeout)
            raw_socket.settimeout(timeout)
            if target.scheme == "https":
                raw_socket = ssl.create_default_context().wrap_socket(
                    raw_socket, server_hostname=target.host
                )
            connection = http.client.HTTPConnection(target.host, target.port, timeout=timeout)
            connection.sock = raw_socket
            break
        except OSError as error:
            last_error = error
    if connection is None:
        raise OSError("all validated source addresses failed") from last_error
    request_headers = {
        "Host": _host_header(target),
        "User-Agent": "lan-music-bridge/0.1",
        "Connection": "close",
        **(headers or {}),
    }
    try:
        connection.request("GET", target.path, headers=request_headers)
        response = connection.getresponse()
        if response.status not in {200, 206}:
            raise OSError(f"source returned HTTP {response.status}")
        yield response
    finally:
        connection.close()
