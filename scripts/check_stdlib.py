#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import ast
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
allowed = set(sys.stdlib_module_names) | {"lan_music_bridge", "tests"}
unexpected: dict[str, set[str]] = {}
for path in sorted((root / "src").rglob("*.py")) + sorted((root / "tests").rglob("*.py")):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [item.name.split(".", 1)[0] for item in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module.split(".", 1)[0]]
        for name in names:
            if name not in allowed:
                unexpected.setdefault(str(path.relative_to(root)), set()).add(name)
if unexpected:
    for path, names in unexpected.items():
        print(f"unexpected dependency in {path}: {', '.join(sorted(names))}")
    raise SystemExit(1)
print("stdlib dependency audit passed")
