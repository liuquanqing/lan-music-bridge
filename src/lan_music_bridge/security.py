# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Mapping
from .config import Settings
from .net import resolve_source

SENSITIVE_KEY = re.compile(
    r"(?i)(authorization|cookie|credential|password|secret|signature|token|url|uri|vkey|key)"
)


def fingerprint(value: str | bytes) -> str:
    raw = value.encode("utf-8", "surrogatepass") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()[:12]


def redact_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): (
                f"<redacted:{fingerprint(str(item))}>"
                if SENSITIVE_KEY.search(str(key))
                else redact_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_value(item) for item in value]
    if isinstance(value, str) and ("?" in value or "://" in value):
        return f"<redacted:{fingerprint(value)}>"
    return value


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    safe = {"event": event, **redact_value(fields)}
    logger.info(json.dumps(safe, ensure_ascii=True, sort_keys=True))


def validate_source_url(url: str, settings: Settings) -> str:
    resolve_source(url, settings)
    return url
