"""SQLite connection and schema apply. schema.sql stays valid PostgreSQL."""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(target: str) -> sqlite3.Connection:
    if target.startswith("postgres://") or target.startswith("postgresql://"):
        raise SystemExit(
            "FEEDS_DATABASE_URL points at Postgres. Apply schema.sql with the "
            "platform database tools. The feeds runner uses a sqlite file so "
            "tests need no database server."
        )
    if target.startswith("sqlite:///"):
        target = target[len("sqlite:///") :]
    if target == ":memory:":
        conn = sqlite3.connect(":memory:")
    else:
        path = Path(target)
        if path.parent and str(path.parent) not in ("", "."):
            path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    script = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(script)
    conn.commit()
