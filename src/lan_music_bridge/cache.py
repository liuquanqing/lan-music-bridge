# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
import time
from contextlib import closing
from pathlib import Path
from typing import BinaryIO

from .config import Settings
from .models import CacheEntry
from .net import open_source
from .security import fingerprint


class CacheStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.cache_dir
        self.blobs = self.root / "blobs"
        self.tmp = self.root / "tmp"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o750)
        self.blobs.mkdir(parents=True, exist_ok=True, mode=0o750)
        self.tmp.mkdir(parents=True, exist_ok=True, mode=0o750)
        self.db_path = self.root / "cache.sqlite3"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with closing(self._connect()) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """CREATE TABLE IF NOT EXISTS media (
                    digest TEXT PRIMARY KEY,
                    size INTEGER NOT NULL,
                    content_type TEXT NOT NULL,
                    source_fingerprint TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    accessed_at REAL NOT NULL,
                    pinned INTEGER NOT NULL DEFAULT 0
                )"""
            )

    def _write_stream(
        self,
        source: BinaryIO,
        content_type: str,
        source_fingerprint: str,
        max_bytes: int,
        expected_bytes: int | None = None,
    ) -> CacheEntry:
        digest = hashlib.sha256()
        size = 0
        fd, temporary_name = tempfile.mkstemp(prefix="ingest-", dir=self.tmp)
        try:
            with os.fdopen(fd, "wb") as target:
                while True:
                    block = source.read(1024 * 1024)
                    if not block:
                        break
                    size += len(block)
                    if size > max_bytes:
                        raise ValueError("media exceeds configured size limit")
                    digest.update(block)
                    target.write(block)
                if expected_bytes is not None and size != expected_bytes:
                    raise ValueError("media length does not match Content-Length")
                target.flush()
                os.fsync(target.fileno())
            hexdigest = digest.hexdigest()
            final_path = self.blobs / hexdigest
            if final_path.exists():
                os.unlink(temporary_name)
            else:
                os.replace(temporary_name, final_path)
                os.chmod(final_path, 0o640)
            now = time.time()
            with closing(self._connect()) as db, db:
                db.execute(
                    """INSERT INTO media
                    (digest, size, content_type, source_fingerprint, created_at, accessed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(digest) DO UPDATE SET accessed_at=excluded.accessed_at""",
                    (hexdigest, size, content_type, source_fingerprint, now, now),
                )
            self.evict_to_limit()
            try:
                return self.get(hexdigest)
            except KeyError as error:
                raise ValueError(
                    "cache quota cannot fit media without evicting pinned entries"
                ) from error
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    def ingest_file(self, path: str | Path, content_type: str = "application/octet-stream") -> CacheEntry:
        source_path = Path(path).resolve(strict=True)
        if not source_path.is_file():
            raise ValueError("local source must be a regular file")
        with source_path.open("rb") as source:
            return self._write_stream(
                source,
                content_type,
                f"file:{fingerprint(str(source_path))}",
                self.settings.source_max_bytes,
            )

    def ingest_url(self, url: str) -> CacheEntry:
        with open_source(url, self.settings, timeout=20) as response:
            declared = response.headers.get("Content-Length")
            expected_bytes = None
            if declared is not None:
                try:
                    expected_bytes = int(declared)
                except ValueError as error:
                    raise ValueError("invalid Content-Length") from error
                if expected_bytes < 0:
                    raise ValueError("invalid Content-Length")
            if expected_bytes is not None and expected_bytes > self.settings.source_max_bytes:
                raise ValueError("media exceeds configured size limit")
            content_type = response.headers.get_content_type()
            return self._write_stream(
                response,
                content_type,
                f"url:{fingerprint(url)}",
                self.settings.source_max_bytes,
                expected_bytes,
            )

    def get(self, digest: str) -> CacheEntry:
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise KeyError(digest)
        with closing(self._connect()) as db, db:
            row = db.execute("SELECT * FROM media WHERE digest=?", (digest,)).fetchone()
            if row is None:
                raise KeyError(digest)
            path = self.blobs / digest
            if not path.is_file() or path.stat().st_size != row["size"]:
                raise KeyError(digest)
            db.execute("UPDATE media SET accessed_at=? WHERE digest=?", (time.time(), digest))
        return CacheEntry(
            digest=digest,
            path=path,
            size=int(row["size"]),
            content_type=str(row["content_type"]),
            source_fingerprint=str(row["source_fingerprint"]),
            pinned=bool(row["pinned"]),
        )

    def pin(self, digest: str, pinned: bool = True) -> None:
        self.get(digest)
        with closing(self._connect()) as db, db:
            db.execute("UPDATE media SET pinned=? WHERE digest=?", (int(pinned), digest))

    def stats(self) -> dict[str, int]:
        with closing(self._connect()) as db, db:
            row = db.execute("SELECT COUNT(*) AS entries, COALESCE(SUM(size), 0) AS bytes FROM media").fetchone()
        return {"entries": int(row["entries"]), "bytes": int(row["bytes"])}

    def evict_to_limit(self) -> list[str]:
        removed: list[str] = []
        with closing(self._connect()) as db, db:
            total = int(db.execute("SELECT COALESCE(SUM(size), 0) FROM media").fetchone()[0])
            rows = db.execute(
                "SELECT digest, size FROM media WHERE pinned=0 ORDER BY accessed_at ASC"
            ).fetchall()
            for row in rows:
                if total <= self.settings.cache_max_bytes:
                    break
                path = self.blobs / row["digest"]
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
                db.execute("DELETE FROM media WHERE digest=?", (row["digest"],))
                total -= int(row["size"])
                removed.append(str(row["digest"]))
        return removed

    def clear_temporary_files(self) -> None:
        for entry in self.tmp.iterdir():
            if entry.is_file():
                entry.unlink()
