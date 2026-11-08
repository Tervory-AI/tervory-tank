"""Offline Radix unit-test fixtures, excluded from the shipped room image."""
from copy import deepcopy
from typing import Any
from gates_memory import memory_kinds, _text_has_secret, is_tenant_wide_kind

FIXED_FAKE_PER_CALL = {"cost_usd": 0.05, "tokens_in": 10, "tokens_out": 3}

class FakeMemory:
    """In-process fake for offline gates 7+8 tests. No network."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.recalls = 0
        self.remembers = 0
        self.forgets = 0

    async def remember(
        self, tenant_id: str, text: str, kind: str, source: str, *,
        meta: dict | None = None, record_id: str | None = None,
        user_id: str | None = None, tenant_wide: bool = False, **_: Any,
    ) -> dict[str, Any]:
        if kind not in memory_kinds():
            raise ValueError("unsupported Radix memory kind")
        if _text_has_secret(text):
            raise ValueError("Radix memory refuses secret-bearing text")
        if not str(text).strip():
            raise ValueError("Radix memory refuses empty remember text")
        tenant = str(tenant_id)
        payload_meta = dict(meta or {})
        wide = bool(tenant_wide) or is_tenant_wide_kind(kind)
        if wide:
            payload_meta.pop("user_id", None)
        else:
            uid = str(user_id or payload_meta.get("user_id") or "").strip()
            if not uid:
                raise ValueError("missing user_id refused for personal Radix memory kind")
            payload_meta["user_id"] = uid
        meta = payload_meta
        if record_id is not None:
            for row in self.rows:
                if row["id"] == str(record_id) and row["tenant_id"] == tenant:
                    row["text"] = text
                    row["kind"] = kind
                    row["source"] = source
                    row["meta"] = dict(meta or {})
                    self.remembers += 1
                    return {"id": row["id"], "seen": self.remembers, "updated": True}
            raise ValueError("remember update refused: memory not found for tenant")
        row = {
            "id": f"mem-{len(self.rows) + 1}",
            "tenant_id": tenant,
            "text": text,
            "kind": kind,
            "source": source,
            "meta": dict(meta or {}),
        }
        self.rows.append(row)
        self.remembers += 1
        return {"id": row["id"], "seen": self.remembers}

    async def recall(
        self, tenant_id: str, query: str, *, kind: str | None = None,
        limit: int | None = None, user_id: str | None = None, **_: Any,
    ) -> list[dict[str, Any]]:
        """Simulate PROPOSED Hermes SQL user scope (unapplied patch)."""
        self.recalls += 1
        tenant = str(tenant_id)
        actor = str(user_id).strip() if user_id is not None else ""
        matches = []
        for row in self.rows:
            if row["tenant_id"] != tenant:
                continue
            if kind is not None and row["kind"] != kind:
                continue
            meta = row.get("meta") or {}
            row_user = str(meta.get("user_id") or "")
            if actor:
                # Personal rows for other users never return; unscoped only if tenant-wide.
                if row_user and row_user != actor:
                    continue
                if not row_user and not is_tenant_wide_kind(str(row.get("kind") or "")):
                    continue
            if not (
                not query
                or query.lower() in row["text"].lower()
                or query == meta.get("task_key")
                or query == meta.get("control")
            ):
                continue
            matches.append(row)
        if limit is not None:
            matches = matches[:limit]
        return deepcopy(matches)

    async def forget(self, memory_id: str, tenant_id: str, *, user_id: str | None = None) -> None:
        tenant = str(tenant_id)
        before = len(self.rows)
        self.rows = [
            row for row in self.rows if not (row["id"] == memory_id and row["tenant_id"] == tenant)
        ]
        if len(self.rows) < before:
            self.forgets += 1

    async def records(self, tenant_id: str, *, user_id: str | None = None, tier: str = "client") -> list[dict[str, Any]]:
        del tier
        return deepcopy([row for row in self.rows if row["tenant_id"] == str(tenant_id)
                         and (user_id is None or row["meta"].get("user_id") == user_id)])


