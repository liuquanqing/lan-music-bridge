# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import urllib.error
import urllib.request
from pathlib import Path

from .config import Settings
from .http_server import BridgeServers
from .runtime import BridgeRuntime

DEFAULT_CONFIG = os.environ.get("LAN_MUSIC_BRIDGE_CONFIG", "/etc/lan-music-bridge/config.toml")


def admin_request(settings: Settings, path: str, payload: dict[str, object] | None = None) -> object:
    url = f"http://{settings.admin_host}:{settings.admin_port}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="GET" if payload is None else "POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try:
            result = json.load(error)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            result = {}
        finally:
            error.close()
        message = result.get("error") if isinstance(result, dict) else None
        raise SystemExit(f"request failed: {message or 'server rejected the request'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lan-music-bridge")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="run media and loopback admin servers")
    commands.add_parser("validate-config", help="validate configuration without starting")
    commands.add_parser("status", help="read the redacted daemon status")
    commands.add_parser("discover", help="discover compatible renderers")
    play = commands.add_parser("play", help="play a stream or cached local media")
    play.add_argument("--renderer", required=True, help="exact UDN or friendly name")
    play.add_argument("--mode", choices=("stream", "local"), required=True)
    source = play.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", help="local file path (local mode only)")
    source.add_argument(
        "--url-stdin",
        action="store_true",
        help="read source URL from stdin so signed URLs do not enter shell history",
    )
    play.add_argument("--title", default="LAN media")
    play.add_argument(
        "--content-type",
        default="",
        help="explicit media MIME type for strict renderers",
    )
    queue = commands.add_parser(
        "queue", help="replace an OpenHome Playlist from a JSON file"
    )
    queue.add_argument("--renderer", required=True, help="exact UDN or friendly name")
    queue.add_argument(
        "--playlist",
        required=True,
        help="JSON array file, or - to read it from stdin",
    )
    control = commands.add_parser("control", help="send play, pause, or stop")
    control.add_argument("--renderer", required=True)
    control.add_argument("action", choices=("play", "pause", "stop"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_file(args.config)
    if args.command == "validate-config":
        print("configuration valid")
        return 0
    if args.command == "serve":
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        runtime = BridgeRuntime(settings)
        servers = BridgeServers(runtime)

        def stop(_signum, _frame):  # noqa: ANN001
            import threading

            threading.Thread(target=servers.shutdown, daemon=True).start()

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        servers.serve_forever()
        return 0
    if args.command == "status":
        result = admin_request(settings, "/v1/status")
    elif args.command == "discover":
        result = admin_request(settings, "/v1/discover", {})
    elif args.command == "play":
        if args.file:
            if args.mode != "local":
                raise SystemExit("--file requires --mode local")
            media_source = str(Path(args.file).resolve())
        else:
            media_source = sys.stdin.readline().strip()
            if not media_source:
                raise SystemExit("stdin did not contain a URL")
        result = admin_request(
            settings,
            "/v1/play",
            {
                "renderer": args.renderer,
                "mode": args.mode,
                "source": media_source,
                "title": args.title,
                "content_type": args.content_type,
            },
        )
    elif args.command == "queue":
        playlist_path = None if args.playlist == "-" else Path(args.playlist).resolve()
        if playlist_path is None:
            value = json.load(sys.stdin)
            base = Path.cwd()
        else:
            with playlist_path.open("r", encoding="utf-8") as source:
                value = json.load(source)
            base = playlist_path.parent
        if not isinstance(value, list):
            raise SystemExit("playlist must be a JSON array")
        items: list[object] = []
        for value_item in value:
            if not isinstance(value_item, dict):
                items.append(value_item)
                continue
            item = dict(value_item)
            source_value = item.get("source")
            if (
                item.get("mode") == "local"
                and isinstance(source_value, str)
                and not source_value.startswith(("http://", "https://"))
            ):
                item["source"] = str((base / source_value).resolve())
            items.append(item)
        result = admin_request(
            settings,
            "/v1/queue",
            {"renderer": args.renderer, "items": items},
        )
    elif args.command == "control":
        result = admin_request(
            settings,
            "/v1/control",
            {"renderer": args.renderer, "action": args.action},
        )
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
