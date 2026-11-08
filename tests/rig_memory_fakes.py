"""Offline Rig unit-test memory and provider tariff; never shipped in the room."""
from copy import deepcopy
from typing import Any
from rig_memory import memory_kinds, _text_has_secret

FIXED_FAKE_PER_CALL = {"cost_usd": 0.05, "tokens_in": 10, "tokens_out": 3}

class FakeMemory:
    """In-process fake for offline gates 7+8 tests. No network."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.recalls = 0
        self.remembers = 0
        self.forgets = 0

    async def remember(
        self,
        tenant_id: str,
        text: str,
        kind: str,
        source: str,
        *,
        meta: dict | None = None,
        user_id: str | None = None,
        tenant_wide: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        if kind not in memory_kinds():
            raise ValueError("unsupported Rig memory kind")
        if _text_has_secret(text):
            raise ValueError("Rig memory refuses secret-bearing text")
        payload_meta = dict(meta or {})
        if tenant_wide:
            payload_meta.pop("user_id", None)
        else:
            uid = (user_id or payload_meta.get("user_id") or "").strip()
            if not uid:
                raise ValueError("user_id required for personal memory")
            payload_meta["user_id"] = uid
        row = {
            "id": f"mem-{len(self.rows) + 1}",
            "tenant_id": str(tenant_id),
            "text": text,
            "kind": kind,
            "source": source,
            "meta": payload_meta,
        }
        self.rows.append(row)
        self.remembers += 1
        return {"id": row["id"], "seen": self.remembers}

    async def records(self, tenant_id: str, *, tier: str = "client", user_id: str | None = None, **_: Any) -> list[dict[str, Any]]:
        del tier
        tenant = str(tenant_id)
        rows = [row for row in self.rows if row["tenant_id"] == tenant]
        uid = (user_id or "").strip() or None
        if uid:
            filtered = []
            for row in rows:
                meta = row.get("meta") or {}
                owner = str(meta.get("user_id") or "").strip()
                if owner == uid or (not owner and row.get("kind") == "rig.store_preference"):
                    filtered.append(row)
            rows = filtered
        return deepcopy(rows)

    async def forget(self, memory_id: str, tenant_id: str, *, user_id: str | None = None) -> None:
        tenant = str(tenant_id)
        wanted = str(memory_id)
        before = len(self.rows)
        self.rows = [
            row for row in self.rows
            if not (row["id"] == wanted and row["tenant_id"] == tenant
                    and (user_id is None or (row.get("meta") or {}).get("user_id") == user_id))
        ]
        if len(self.rows) < before:
            self.forgets += 1

    async def recall(
        self,
        tenant_id: str,
        query: str,
        *,
        kind: str | None = None,
        limit: int | None = None,
        user_id: str | None = None,
        **_: Any,
    ) -> list[dict[str, Any]]:
        self.recalls += 1
        tenant = str(tenant_id)
        uid = (user_id or "").strip() or None
        matches = []
        for row in self.rows:
            if row["tenant_id"] != tenant:
                continue
            if kind is not None and row["kind"] != kind:
                continue
            if query and query.lower() not in row["text"].lower() and query != (row.get("meta") or {}).get("task_key"):
                continue
            meta = row.get("meta") or {}
            owner = str(meta.get("user_id") or "").strip()
            if uid:
                # Mirror Hermes SQL user scope: own personal OR tenant-wide unscoped.
                if owner and owner != uid:
                    continue
                if not owner and row.get("kind") != "rig.store_preference":
                    continue
            matches.append(row)
        if limit is not None:
            matches = matches[:limit]
        return deepcopy(matches)


