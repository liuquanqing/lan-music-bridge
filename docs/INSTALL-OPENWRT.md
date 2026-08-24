# OpenWrt packaging

The OpenWrt package is source-only and depends on the distribution's Python standard
library modules. It does not include binary wheels or third-party provider code.

Place or symlink `packaging/openwrt` into an OpenWrt buildroot package directory while
keeping the repository layout available two levels above it, then select
`Utilities -> lan-music-bridge` in `menuconfig`.

The package installs:

- Python sources below `/usr/libexec/lan-music-bridge`;
- `/etc/init.d/lan-music-bridge` as a procd service;
- `/etc/config/lan-music-bridge` for enable/config-path control;
- `/etc/lan-music-bridge/config.toml` as a conffile.

After installation, edit the TOML file and validate before enabling:

```sh
/usr/bin/python3 -m lan_music_bridge \
  --config /etc/lan-music-bridge/config.toml validate-config
/etc/init.d/lan-music-bridge enable
/etc/init.d/lan-music-bridge start
wget -qO- http://127.0.0.1:49500/health
```

Keep the service disabled in firmware images used for staged migration. Enable it
only after the previous publisher is stopped or identities/ports are deliberately
isolated. Roll back by stopping/disabling this service and reinstalling the previous
package version; configuration and cache should be backed up separately.

The init script never modifies network, firewall, DNS, WAN, or renderer settings.
