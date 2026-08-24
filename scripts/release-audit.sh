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

if find . -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '*.whl' -o -name '*.media' -o -name '*.sqlite3' \) -print | grep -q .; then
	echo "release audit failed: generated/binary/runtime files present" >&2
	exit 1
fi
if find . -type d \( -name '*.egg-info' -o -name build -o -name dist -o -name __pycache__ \) -print | grep -q .; then
	echo "release audit failed: generated directories present" >&2
	exit 1
fi

if rg -I -l -g '!scripts/release-audit.sh' \
	'(BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|AKIA[A-Z0-9]{16}|ASIA[A-Z0-9]{16}|glpat-[A-Za-z0-9_-]{10,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})' . | grep -q .; then
	echo "release audit failed: high-confidence secret pattern" >&2
	exit 1
fi

if rg -I -l -g '!scripts/release-audit.sh' \
	'(10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|192\.168\.[0-9]{1,3}\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3})' . | grep -q .; then
	echo "release audit failed: private IPv4 literal" >&2
	exit 1
fi

if rg -I -l -g '!scripts/release-audit.sh' \
	'(?i)(audimaxim|gustard|qplay|qq music|netease)' . | grep -q .; then
	echo "release audit failed: private/vendor brand residue" >&2
	exit 1
fi

missing_spdx=$(find src tests scripts -type f \( -name '*.py' -o -name '*.sh' \) \
	-exec grep -L 'SPDX-License-Identifier: Apache-2.0' {} +)
if [ -n "$missing_spdx" ]; then
	echo "release audit failed: missing SPDX header" >&2
	exit 1
fi

echo "release audit passed"
