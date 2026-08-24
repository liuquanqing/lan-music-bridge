#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -eu

[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }
purge=0
[ "${1:-}" = "--purge" ] && purge=1
systemctl disable --now lan-music-bridge 2>/dev/null || true
rm -f /etc/systemd/system/lan-music-bridge.service
systemctl daemon-reload
rm -rf /opt/lan-music-bridge
if [ "$purge" -eq 1 ]; then
	echo "purging /etc/lan-music-bridge and /var/lib/lan-music-bridge"
	rm -rf /etc/lan-music-bridge /var/lib/lan-music-bridge
else
	echo "preserved /etc/lan-music-bridge and /var/lib/lan-music-bridge"
fi
