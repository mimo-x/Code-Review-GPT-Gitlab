from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Store:
    """Versioned JSON records; each write is an atomic SQLite transaction."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS records "
                "(namespace TEXT, key TEXT, value TEXT NOT NULL, PRIMARY KEY(namespace, key))"
            )

    @contextmanager
    def connect(self):
        # dozens of reviews of one state dir write their caches at once; 30 s was too short
        db = sqlite3.connect(self.path, timeout=180)
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, namespace: str, key: str) -> dict | list | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT value FROM records WHERE namespace=? AND key=?", (namespace, key)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, namespace: str, key: str, value: dict | list) -> None:
        payload = json.dumps(value, ensure_ascii=True, sort_keys=True)
        with self.connect() as db:
            db.execute(
                "INSERT INTO records VALUES (?, ?, ?) "
                "ON CONFLICT(namespace, key) DO UPDATE SET value=excluded.value",
                (namespace, key, payload),
            )

    def find_prefix(self, namespace: str, prefix: str) -> dict | list | None:
        """The record whose key starts with prefix, if exactly one does."""
        escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with self.connect() as db:
            rows = db.execute(
                "SELECT value FROM records WHERE namespace=? AND key LIKE ? ESCAPE '\\' LIMIT 2",
                (namespace, escaped + "%"),
            ).fetchall()
        return json.loads(rows[0][0]) if len(rows) == 1 else None

    def put_many(self, namespace: str, records: dict[str, dict]) -> None:
        rows = [
            (namespace, key, json.dumps(value, ensure_ascii=True, sort_keys=True))
            for key, value in records.items()
        ]
        with self.connect() as db:
            db.executemany(
                "INSERT INTO records VALUES (?, ?, ?) "
                "ON CONFLICT(namespace, key) DO UPDATE SET value=excluded.value",
                rows,
            )
