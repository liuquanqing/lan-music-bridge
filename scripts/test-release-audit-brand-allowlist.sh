#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/lan-music-bridge-brand-audit.XXXXXX")
trap 'find "$work_dir" -depth -delete' EXIT HUP INT TERM

git clone -q "$repo_dir" "$work_dir/repo"
cp "$repo_dir/scripts/release-audit.sh" "$work_dir/repo/scripts/release-audit.sh"
chmod 755 "$work_dir/repo/scripts/release-audit.sh"

# Build the allowed brands in pieces so this self-test does not whitelist itself.
protocol_brand=$(printf '%s%s' 'QP' 'lay')
platform_brand=$(printf '%s %s' 'QQ' 'Music')
printf '\n%s %s compatibility boundary.\n' \
	"$platform_brand" "$protocol_brand" >>"$work_dir/repo/README.md"
git -C "$work_dir/repo" add README.md scripts/release-audit.sh
if ! "$work_dir/repo/scripts/release-audit.sh" >"$work_dir/allowed.log" 2>&1; then
	echo "release audit self-test failed: README brand boundary was rejected" >&2
	exit 1
fi

printf '%s %s private implementation residue\n' \
	"$platform_brand" "$protocol_brand" >"$work_dir/repo/brand-probe.txt"
git -C "$work_dir/repo" add brand-probe.txt
if "$work_dir/repo/scripts/release-audit.sh" >"$work_dir/rejected.log" 2>&1; then
	echo "release audit self-test failed: brand outside README was accepted" >&2
	exit 1
fi
if ! grep -Fq 'release audit failed: restricted brand outside README' "$work_dir/rejected.log"; then
	echo "release audit self-test failed: unexpected brand audit result" >&2
	exit 1
fi

echo "release audit brand allow-list self-test passed"
