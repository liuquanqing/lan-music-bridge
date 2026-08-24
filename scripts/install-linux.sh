#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -eu

[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
install_root=/opt/lan-music-bridge
release_root=$install_root/releases
release_id=$(date -u +%Y%m%dT%H%M%SZ)
release_dir=$release_root/$release_id
config_dir=/etc/lan-music-bridge
state_dir=/var/lib/lan-music-bridge

if ! id lanmusic >/dev/null 2>&1; then
	useradd --system --home-dir "$state_dir" --shell /usr/sbin/nologin lanmusic
fi

install -d -m 0755 "$release_root"
install -d -o root -g lanmusic -m 0750 "$config_dir"
install -d -o lanmusic -g lanmusic -m 0750 "$state_dir" "$state_dir/cache"
python3 -m venv "$release_dir/venv"
"$release_dir/venv/bin/python" -m pip install --no-deps "$repo_dir"

if [ ! -e "$config_dir/config.toml" ]; then
	install -o root -g lanmusic -m 0640 "$repo_dir/config/config.example.toml" "$config_dir/config.toml"
fi
install -o root -g root -m 0644 \
	"$repo_dir/packaging/systemd/lan-music-bridge.service" \
	/etc/systemd/system/lan-music-bridge.service

if [ -L "$install_root/current" ]; then
	old_release=$(readlink -f "$install_root/current")
	ln -sfn "$old_release" "$install_root/previous"
fi
ln -sfn "$release_dir" "$install_root/current.new"
mv -Tf "$install_root/current.new" "$install_root/current"

runuser -u lanmusic -- "$install_root/current/venv/bin/lan-music-bridge" \
	--config "$config_dir/config.toml" validate-config
systemctl daemon-reload
if systemctl is-active --quiet lan-music-bridge; then
	systemctl restart lan-music-bridge
	"$install_root/current/venv/bin/python" -c \
		"import urllib.request; urllib.request.urlopen('http://127.0.0.1:49500/health', timeout=10).read()"
fi
echo "installed release $release_id; review config before enabling service"
