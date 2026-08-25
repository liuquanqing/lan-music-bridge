# LAN Music Bridge

LAN Music Bridge is a vendor-neutral, dependency-free Python service for discovering
UPnP/OpenHome renderers, controlling playback, proxying allow-listed network audio,
and publishing content-addressed local cache files over HTTP with byte-range support.

The project is an alpha release candidate. It has automated protocol and security
tests, but it has not been certified against every renderer or network layout.

## What is included

- SSDP discovery with responder/location origin checks;
- OpenHome Playlist control with UPnP AVTransport fallback;
- network streaming through short-lived in-memory tokens;
- SQLite-indexed, SHA-256-addressed local media cache with atomic writes, pinning,
  quota-aware LRU eviction, and Range delivery;
- a minimal `/health` endpoint that never returns titles, device addresses, source
  URLs, tokens, cookies, or queue metadata;
- a loopback-only administration API and CLI;
- a stable publisher adapter boundary for device-local storage integrations;
- systemd and OpenWrt packaging examples, tests, GitHub Actions CI, and release audits.

Private provider resolvers, account login flows, device-specific storage protocols,
firmware files, media, credentials, and household deployment configuration are not
part of this repository.

## Quick start

Requirements: Python 3.11 or newer and a renderer reachable on the same multicast
domain.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
install -d -m 0750 ./var/cache
cp config/config.example.toml ./config.toml
```

Edit `config.toml` before starting. In particular, set `public_base_url` to the
bridge address that the renderer can reach and replace the example source allow-list.

```sh
lan-music-bridge --config ./config.toml validate-config
lan-music-bridge --config ./config.toml serve
```

In another terminal:

```sh
lan-music-bridge --config ./config.toml discover
lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode local --file ./track.flac
printf '%s\n' 'https://media.example/path/to/audio' | \
  lan-music-bridge --config ./config.toml play \
  --renderer 'uuid:your-renderer' --mode stream --url-stdin
```

Passing a signed media URL through stdin keeps it out of shell history. The daemon
keeps stream URLs only in memory and logs only short irreversible fingerprints.

Run the test and release gates with:

```sh
make check
make release-audit
```

## Boundaries

The built-in local publisher serves a fully downloaded immutable file from the
bridge. Copying that file into a renderer's own disk/library is deliberately an
adapter concern because storage and indexing protocols are device-specific. See
[docs/ADAPTERS.md](docs/ADAPTERS.md).

The media listener is intended for trusted LANs. The administration listener is
hard-limited to loopback. Read [SECURITY.md](SECURITY.md) before exposing any port
across VLAN, VPN, guest, or internet boundaries.

This independent project does not claim endorsement, certification, partnership,
or compatibility guarantees from any device, platform, or service provider.

## Documentation

- [Architecture](ARCHITECTURE.md)
- [Security](SECURITY.md)
- [Adapters](docs/ADAPTERS.md)
- [Linux installation and rollback](docs/INSTALL-LINUX.md)
- [OpenWrt packaging](docs/INSTALL-OPENWRT.md)
- [Private deployment boundary](docs/MIGRATION.md)
- [Release checklist](docs/RELEASE.md)
- [Source provenance](PROVENANCE.md)
- [Changelog](CHANGELOG.md)

Licensed under Apache License 2.0.
