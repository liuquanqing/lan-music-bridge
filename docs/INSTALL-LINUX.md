# Linux installation, upgrade, and rollback

The scripts target a systemd host with Python 3.11 or newer. Review them before use.
They create a dedicated `lanmusic` account, versioned virtual environments below
`/opt/lan-music-bridge/releases`, a `current` symlink, and persistent configuration
and cache directories outside the release.

From a verified source checkout:

```sh
sudo ./scripts/install-linux.sh
sudoedit /etc/lan-music-bridge/config.toml
sudo systemctl enable --now lan-music-bridge
curl --fail http://127.0.0.1:49500/health
```

The example configuration is not production-ready. Replace the documentation address,
source allow-list, cache size, and discovery source IP. Apply host firewall rules so
only renderer networks can reach the media port. The admin port must remain loopback.

## Upgrade

Check out the exact reviewed commit, rerun the release gates, then:

```sh
sudo ./scripts/upgrade-linux.sh
```

The installer creates a new release without modifying the prior release, updates
`previous` and `current` symlinks atomically, validates the configuration, restarts
the service, and checks the local health endpoint.

## Rollback

```sh
sudo ./scripts/rollback-linux.sh
```

Rollback swaps `current` and `previous`, restarts, and verifies health. Cache and
configuration are forward data and remain in place; back them up before an upgrade
that changes their schema.

## Uninstall

```sh
sudo ./scripts/uninstall-linux.sh
```

This removes the unit and application releases but preserves configuration and cache.
Use `--purge` only after separately backing up and confirming the exact persistent
paths printed by the script.
