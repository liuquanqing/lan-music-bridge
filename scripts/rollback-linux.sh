#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -eu

[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }
install_root=/opt/lan-music-bridge
current=$(readlink -f "$install_root/current")
previous=$(readlink -f "$install_root/previous")
case "$current:$previous" in
	"$install_root"/releases/*:"$install_root"/releases/*) ;;
	*) echo "refusing rollback: release symlinks escaped expected root" >&2; exit 1 ;;
esac

ln -sfn "$previous" "$install_root/current.new"
mv -Tf "$install_root/current.new" "$install_root/current"
ln -sfn "$current" "$install_root/previous"
systemctl restart lan-music-bridge
"$install_root/current/venv/bin/python" -c \
	"import urllib.request; urllib.request.urlopen('http://127.0.0.1:49500/health', timeout=10).read()"
echo "rolled back to $(basename "$previous")"
