"""Gates 7+8: Tisan recalls before its brain and remembers after.

This module uses the room's existing chassis memory client (``ctx.memory``),
which reaches Tank's tenant-scoped Hermes memory with the room key. It is not
a second memory system: it adds no store, no collection and no index. Every
row is tenant-scoped by Hermes. User scope is NOT filtered here: Tisan only
passes the verified actor's user_id to the shared client (Tank t51 contract),
and fails closed with SharedMemoryContractMissing while that client lacks it.

What Tisan remembers (``REMEMBERS``) is fixed: brand choices, approved and
rejected sections, quote history, task results with their receipts, user
corrections, and the user's memory on/off setting.

An exact repeat (same tenant, user, task key and input hash) is answered from
memory before any brain or Tank call. Exact lookup uses the SQL record list,
never an embedding search, so a hit costs no model call and no tokens.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import uuid
from typing import Any, Awaitable, Callable

RESULT = "tisan.result"
CORRECTION = "tisan.correction"
BRAND = "tisan.brand"
SECTION = "tisan.section"
QUOTE = "tisan.quote"
SETTING = "tisan.memory_setting"
OUTCOME = "tisan.outcome"
REMEMBERS = {
    BRAND: "brand choices (colours, fonts, logo) the user picked",
    SECTION: "sections the user approved or rejected",
    QUOTE: "quote history",
    RESULT: "task outcome with its Tank receipt",
    CORRECTION: "user corrections; they override earlier results",
    SETTING: "whether this user's memory is on",
    OUTCOME: "each live endpoint outcome (route, method, status, subject)",
}
SOURCE = "tisan:gates-7-8"
# Record types that belong to the whole client, declared for the shared
# contract. Every other kind in REMEMBERS is personal to the signed-in user.
TENANT_WIDE = frozenset({BRAND})
REQUIRED = {"remember": ("user_id", "tenant_wide"), "recall": ("user_id",), "records": ("user_id",), "forget": ("user_id",)}


class SharedMemoryContractMissing(RuntimeError):
    """The shared chassis memory client cannot scope personal records."""


def require_contract(memory: Any) -> None:
    import inspect
    missing = []
    for name, params in REQUIRED.items():
        method = getattr(memory, name, None)
        try:
            have = inspect.signature(method).parameters if method is not None else {}
        except (TypeError, ValueError):
            have = {}
        missing += [f"{name}({p})" for p in params if p not in have]
    if missing:
        raise SharedMemoryContractMissing(
            "shared memory client lacks central user scope: " + ", ".join(missing)
            + "; requires current shared Tank personal-memory contract")


def brain_enabled() -> bool:
    """The existing product switch stays opt-in."""
    return os.environ.get("TISAN_BRAIN_ENABLED", "false").strip().lower() not in {"0", "false", "no", "off"}


def input_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def scope_key(tenant: str, user: str, task_key: str, digest: str) -> str:
    return hashlib.sha256("\x1f".join((tenant, user, task_key, digest)).encode()).hexdigest()


def _uuid(value: Any, name: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f"{name} must be a UUID") from None


def trusted_user(value: Any) -> str:
    """The caller passes only an identity its guard already verified (never a request body field)."""
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_.:@|-]{1,200}", value) is None:
        raise ValueError("verified user is required")
    return value


def free_receipt(memory_id: str | None, source: str, would_have: dict | None = None) -> dict:
    """An answer served from memory: $0 now, plus what the original paid run cost."""
    would_have = would_have or {}
    return {"source": source, "memory_id": memory_id, "answered_from_memory": True, "paid_calls": 0,
            "cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0, "ledger_ids": [],
            "would_have_cost_usd": would_have.get("cost_usd"),
            "would_have_paid_calls": would_have.get("paid_calls"),
            "would_have_tokens_in": would_have.get("tokens_in"),
            "would_have_tokens_out": would_have.get("tokens_out")}


MEMORY_UNAVAILABLE = "memory unavailable"


def is_outage(exc: BaseException) -> bool:
    """A Hermes service outage (unreachable, timeout or 5xx), never a scope or validation error."""
    if isinstance(exc, SharedMemoryContractMissing):
        return False
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    return isinstance(exc, RuntimeError) and re.fullmatch(r"hermes (unreachable|answered 5\d\d)", str(exc)) is not None


def tank_receipt(replies: list[dict]) -> dict:
    """Summarise Tank route replies; missing prices stay None (pending), never guessed."""
    costs = [r.get("cost_usd") for r in replies]
    return {"source": "tank", "memory_id": None, "paid_calls": len(replies),
            "cost_usd": None if any(c is None for c in costs) else round(sum(float(c) for c in costs), 10),
            "tokens_in": sum(int(r.get("tokens_in") or 0) for r in replies),
            "tokens_out": sum(int(r.get("tokens_out") or 0) for r in replies),
            "ledger_ids": [r["ledger_id"] for r in replies if r.get("ledger_id")]}


class GateMemory:
    def __init__(self, memory: Any, tenant: str, user: str) -> None:
        if memory is None:
            raise ValueError("memory client is required")
        require_contract(memory)
        self.memory = memory
        self.tenant = _uuid(tenant, "tenant")
        self.user = trusted_user(user)

    async def _rows(self) -> list[dict]:
        # Hermes returns only this user's personal rows and declared tenant-wide rows.
        rows = await self.memory.records(self.tenant, user_id=self.user)
        for row in rows:
            if row.get("tenant_id") not in (None, self.tenant):
                raise RuntimeError("Memory tenant boundary failed")
        return [row for row in rows if row.get("kind") in REMEMBERS]

    async def _personal(self) -> list[dict]:
        return [r for r in await self._rows() if (r.get("meta") or {}).get("user_id") == self.user]

    async def view(self) -> list[dict]:
        """Everything Tisan remembers for this user, oldest first."""
        return sorted(await self._rows(), key=lambda r: int((r.get("meta") or {}).get("seq") or 0))

    async def _remember(self, kind: str, text: str, meta: dict, *, tenant_wide: bool = False) -> dict:
        seq = max([int((r.get("meta") or {}).get("seq") or 0) for r in await self._rows()] + [0]) + 1
        return await self.memory.remember(self.tenant, text, kind, SOURCE, confidence=1.0,
                                          meta={**meta, "seq": seq}, index=False,
                                          user_id=None if tenant_wide else self.user,
                                          tenant_wide=tenant_wide)

    async def enabled(self) -> bool:
        settings = [r for r in await self.view() if r.get("kind") == SETTING]
        return bool((settings[-1].get("meta") or {}).get("enabled", True)) if settings else True

    async def set_enabled(self, flag: bool) -> dict:
        for row in [r for r in await self._personal() if r.get("kind") == SETTING]:
            await self.memory.forget(row["id"], self.tenant, user_id=self.user)
        return await self._remember(SETTING, "memory " + ("on" if flag else "off"), {"enabled": bool(flag)})

    async def forget(self, memory_id: str | None = None) -> int:
        """Forget one of this user's rows, or all of them (the setting survives)."""
        rows = [r for r in await self._personal() if r.get("kind") != SETTING]
        if memory_id is not None:
            rows = [r for r in rows if r.get("id") == memory_id]
            if not rows:
                raise KeyError("memory not found for this user")
        for row in rows:
            await self.memory.forget(row["id"], self.tenant, user_id=self.user)
        return len(rows)

    async def edit(self, memory_id: str, value: Any) -> dict:
        """Replace one remembered value for this user; results become corrections."""
        rows = [r for r in await self._personal() if r.get("id") == memory_id and r.get("kind") != SETTING]
        if not rows:
            raise KeyError("memory not found for this user")
        row, meta = rows[0], dict(rows[0].get("meta") or {})
        await self.memory.forget(row["id"], self.tenant, user_id=self.user)
        if row.get("kind") in {RESULT, CORRECTION}:
            meta.pop("receipt", None)
            return await self._remember(CORRECTION, str(meta.get("task_key")) + " correction",
                                        {"key": meta.get("key"), "task_key": meta.get("task_key"), "result": value})
        meta.pop("seq", None)
        meta.pop("user_id", None)
        meta.pop("scope", None)
        return await self._remember(row["kind"], json.dumps({"subject": meta.get("subject"), "value": value},
                                    ensure_ascii=False), {**meta, "value": value})

    async def remember_choice(self, kind: str, subject: str, value: Any) -> dict | None:
        if kind not in {BRAND, SECTION, QUOTE}:
            raise ValueError("unsupported memory kind")
        if not await self.enabled():
            return None
        return await self._remember(kind, json.dumps({"subject": subject, "value": value}, ensure_ascii=False),
                                    {"subject": subject, "value": value}, tenant_wide=kind in TENANT_WIDE)

    async def remember_outcome(self, route: str, method: str, status: int, subject: str | None) -> dict | None:
        if not await self.enabled():
            return None
        return await self._remember(OUTCOME, f"{method} {route} {status}",
                                    {"route": route, "method": method, "status": status, "subject": subject})

    async def lookup(self, task_key: str, payload: Any) -> dict | None:
        key = scope_key(self.tenant, self.user, task_key, input_hash(payload))
        rows = [r for r in await self.view() if (r.get("meta") or {}).get("key") == key
                and r.get("kind") in {RESULT, CORRECTION}]
        return rows[-1] if rows else None

    async def remember_result(self, task_key: str, payload: Any, result: Any, receipt: dict) -> dict:
        key = scope_key(self.tenant, self.user, task_key, input_hash(payload))
        return await self._remember(RESULT, task_key + " result", {"key": key, "task_key": task_key,
                                    "result": result, "receipt": receipt})

    async def correct(self, task_key: str, payload: Any, result: Any) -> dict:
        """Store a correction and forget the stale results it replaces."""
        key = scope_key(self.tenant, self.user, task_key, input_hash(payload))
        for row in await self._personal():
            meta = row.get("meta") or {}
            if meta.get("key") == key and row.get("kind") in {RESULT, CORRECTION}:
                await self.memory.forget(row["id"], self.tenant, user_id=self.user)
        return await self._remember(CORRECTION, task_key + " correction", {"key": key, "task_key": task_key,
                                    "result": result})


Brain = Callable[[], Awaitable[tuple[Any, dict]]]


async def run(memory: Any, tenant: str, user: str, task_key: str, payload: Any, brain: Brain) -> dict:
    """Recall, then (only on a miss) run the brain through Tank, then remember the outcome."""
    # Invalid tenant/user and a missing shared contract raise here: refused, never an outage.
    gate = GateMemory(memory, tenant, user)
    try:
        on = await gate.enabled()
        hit = await gate.lookup(task_key, payload) if on else None
    except Exception as exc:
        if not is_outage(exc):
            raise
        return await _without_memory(brain)
    if hit is not None:
        meta = hit.get("meta") or {}
        source = "correction" if hit.get("kind") == CORRECTION else "memory"
        return {"result": copy.deepcopy(meta["result"]),
                "receipt": free_receipt(hit.get("id"), source, meta.get("receipt")),
                "memory": {"hit": True, "memory_id": hit.get("id"), "enabled": True}}
    result, receipt = await brain()
    receipt = {**receipt, "answered_from_memory": False}
    try:
        saved = await gate.remember_result(task_key, payload, result, receipt) if on else None
    except Exception as exc:
        if not is_outage(exc):
            raise
        return {"result": result, "receipt": {**receipt, "memory_id": None, "memory": MEMORY_UNAVAILABLE},
                "memory": {"hit": False, "memory_id": None, "enabled": None, "unavailable": True}}
    receipt = {**receipt, "memory_id": saved.get("id") if saved else None}
    return {"result": result, "receipt": receipt,
            "memory": {"hit": False, "memory_id": receipt["memory_id"], "enabled": on}}


async def _without_memory(brain: Brain) -> dict:
    """Memory service outage: answer without memory, never from a stored repeat, and say so."""
    result, receipt = await brain()
    return {"result": result, "receipt": {**receipt, "answered_from_memory": False, "memory_id": None,
                                          "memory": MEMORY_UNAVAILABLE},
            "memory": {"hit": False, "memory_id": None, "enabled": None, "unavailable": True}}
