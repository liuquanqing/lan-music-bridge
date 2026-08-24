#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/lan-music-bridge-audit.XXXXXX")
trap 'find "$work_dir" -depth -delete' EXIT HUP INT TERM

git clone -q "$repo_dir" "$work_dir/repo"
cp "$repo_dir/scripts/release-audit.sh" "$work_dir/repo/scripts/release-audit.sh"
chmod 755 "$work_dir/repo/scripts/release-audit.sh"

# Construct the synthetic value in pieces so this self-test is not itself a
# match. The probe is tracked and hidden, proving the index scan covers dotfiles.
printf '%s%s\n' 'gl' 'pat-0123456789abcdef' >"$work_dir/repo/.release-audit-dotfile-probe"
git -C "$work_dir/repo" add scripts/release-audit.sh .release-audit-dotfile-probe

if "$work_dir/repo/scripts/release-audit.sh" >"$work_dir/audit.log" 2>&1; then
	echo "release audit self-test failed: tracked dotfile was not scanned" >&2
	exit 1
fi
if ! grep -Fq 'release audit failed: high-confidence secret pattern' "$work_dir/audit.log"; then
	echo "release audit self-test failed: unexpected audit result" >&2
	exit 1
fi

echo "release audit dotfile self-test passed"
