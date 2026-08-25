#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_dir"

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -W error::ResourceWarning -m unittest discover -s tests -t . -q
python3 scripts/check_stdlib.py
for script in scripts/*.sh packaging/openwrt/files/etc/init.d/lan-music-bridge; do
	sh -n "$script"
done

if git ls-files | grep -Eq '(^|/)[^/]+\.(pyc|pyo|whl|media|sqlite3)$'; then
	echo "release audit failed: tracked generated/binary/runtime files present" >&2
	exit 1
fi
if git ls-files | grep -Eq '(^|/)(build|dist|__pycache__|[^/]+\.egg-info)(/|$)'; then
	echo "release audit failed: tracked generated directories present" >&2
	exit 1
fi

# Retain a working-tree residue check, but prune Git's object database. Exact
# publishable content checks below use the index and therefore cover every path
# returned by git ls-files, including tracked dotfiles.
if find . -path ./.git -prune -o -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '*.whl' -o -name '*.media' -o -name '*.sqlite3' \) -print | grep -q .; then
	echo "release audit failed: generated/binary/runtime files present" >&2
	exit 1
fi
if find . -path ./.git -prune -o -type d \( -name '*.egg-info' -o -name build -o -name dist -o -name __pycache__ \) -print | grep -q .; then
	echo "release audit failed: generated directories present" >&2
	exit 1
fi

if git grep --cached -I -l -E \
	'(BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|AKIA[A-Z0-9]{16}|ASIA[A-Z0-9]{16}|glpat-[A-Za-z0-9_-]{10,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})' \
	-- . ':(exclude)scripts/release-audit.sh' >/dev/null; then
	echo "release audit failed: high-confidence secret pattern" >&2
	exit 1
fi

if git grep --cached -I -l -E \
	'(10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|192\.168\.[0-9]{1,3}\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3})' \
	-- . ':(exclude)scripts/release-audit.sh' >/dev/null; then
	echo "release audit failed: private IPv4 literal" >&2
	exit 1
fi

if git grep --cached -I -l -i -E \
	'(audimaxim|gustard|netease)' \
	-- . ':(exclude)scripts/release-audit.sh' >/dev/null; then
	echo "release audit failed: private/vendor brand residue" >&2
	exit 1
fi

# QQ Music and QPlay may be named only in the public README to describe the
# user-facing compatibility problem. Keep them out of source, config,
# packaging, tests, and every other tracked file.
if git grep --cached -I -l -i -E '(qplay|qq music)' \
	-- . ':(exclude)README.md' ':(exclude)scripts/release-audit.sh' >/dev/null; then
	echo "release audit failed: restricted brand outside README" >&2
	exit 1
fi

missing_spdx=$(git grep --cached -L -F 'SPDX-License-Identifier: Apache-2.0' \
	-- '*.py' '*.sh' 'packaging/openwrt/files/etc/init.d/*' || true)
if [ -n "$missing_spdx" ]; then
	echo "release audit failed: missing SPDX header" >&2
	exit 1
fi

echo "release audit passed"
