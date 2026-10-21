"""Ghost's own volume only. No production database credential or SQL client."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY, tenant TEXT NOT NULL, fingerprint TEXT NOT NULL,
                state TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS active_incident ON incidents(tenant, fingerprint)
                WHERE state != 'solved';
            CREATE TABLE IF NOT EXISTS memories (
                tenant TEXT NOT NULL, incident TEXT NOT NULL, fingerprint TEXT NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY(tenant, incident)
            );
        """)

    def open(self, tenant: str, target: str, signal: str, origin: str) -> dict:
        fingerprint = f"{target}:{signal}"
        existing = self.db.execute(
            "SELECT payload FROM incidents WHERE tenant=? AND fingerprint=? AND state!='solved'",
            (tenant, fingerprint),
        ).fetchone()
        if existing:
            return json.loads(existing[0])
        item = {"id": str(uuid.uuid4()), "target": target, "signal": signal, "origin": origin,
                "state": "open", "steps": [], "cost_usd": 0,
                "created_at": datetime.now(timezone.utc).isoformat()}
        with self.db:
            self.db.execute("INSERT INTO incidents VALUES (?,?,?,?,?,?)",
                            (item["id"], tenant, fingerprint, item["state"], json.dumps(item), item["created_at"]))
        return item

    def get(self, tenant: str, incident: str) -> dict:
        row = self.db.execute("SELECT payload FROM incidents WHERE tenant=? AND id=?", (tenant, incident)).fetchone()
        if row is None:
            raise LookupError("Issue not found.")
        return json.loads(row[0])

    def save(self, tenant: str, item: dict) -> None:
        with self.db:
            self.db.execute("UPDATE incidents SET state=?,payload=? WHERE tenant=? AND id=?",
                            (item["state"], json.dumps(item), tenant, item["id"]))

    def list(self, tenant: str) -> list[dict]:
        rows = self.db.execute("SELECT payload FROM incidents WHERE tenant=? ORDER BY created_at DESC LIMIT 100", (tenant,))
        return [json.loads(row[0]) for row in rows]

    async def recall(self, tenant: str, fingerprint: str) -> list[dict]:
        rows = self.db.execute("SELECT payload FROM memories WHERE tenant=? AND fingerprint=? LIMIT 5", (tenant, fingerprint))
        return [json.loads(row[0]) for row in rows]

    async def remember(self, tenant: str, item: dict) -> None:
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO memories VALUES (?,?,?,?)",
                            (tenant, item["id"], f"{item['target']}:{item['signal']}", json.dumps(item)))

    def gold(self, tenant: str, limit: int) -> list[dict]:
        rows = self.db.execute("SELECT payload FROM memories WHERE tenant=? ORDER BY rowid DESC LIMIT ?", (tenant, limit))
        return [json.loads(row[0]) for row in rows]

    def close(self) -> None:
        self.db.close()
