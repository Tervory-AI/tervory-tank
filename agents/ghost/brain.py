"""Autumbra memory and brain flow (gates 7+8).

Order for every task, like Base's brain bridge: recall first, then corrections
and repeats from memory, then free code passes, and only then the
autumbra-brain service, which routes through Tank and returns receipts. The
outcome, receipt and any correction are remembered afterwards.

Memory is scoped to one tenant (Tank picks the collection from the tenant and
key) and to one user inside it (``meta.user_id``). Secrets are never stored.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from typing import Any, Awaitable, Callable

from .brain_state import BrainState

KINDS = {"incident", "worked_fix", "false_alarm", "maintenance_window", "baseline",
         "correction", "outcome"}
# Repeat task types whose answer depends only on the same normalised input.
CACHE_ELIGIBLE = {"ghost.brain.explain_incident", "ghost.brain.summarise_baseline",
                  "ghost.brain.classify_alert"}
TASK_TYPES = CACHE_ELIGIBLE | {"ghost.brain.plan_fix"}
SECRET = re.compile(
    r"(?i)(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk|pk|rk|ghp|gho|ghs|xox[abprs])[-_][A-Za-z0-9_-]{8,}"
    r"|\bAKIA[0-9A-Z]{16}\b|\b(?:password|passwd|secret|token|api[_-]?key|authorization)\s*[:=]\s*\S+"
    r"|\bbearer\s+[A-Za-z0-9._~+/-]{8,}=*)")
OFF_KEY = "memory_off:"


def contains_secret(text: str) -> bool:
    return bool(SECRET.search(text or ""))


def task_key(task_type: str, text: str) -> str:
    """Exact repeat identity: task type + hash of the exact input. Tenant and user
    scope come from the memory row ownership checks, never from this key."""
    input_hash = hashlib.sha256((text or "").encode()).hexdigest()
    return hashlib.sha256(json.dumps([task_type, input_hash]).encode()).hexdigest()


def user_scope(tenant: str, user: str) -> str:
    """Opaque tenant+user identity. Used as Tank's routed cache case_ref and as
    a memory ownership check; it never carries the raw user id to Tank's cache."""
    return "autumbra-user:" + hashlib.sha256(json.dumps([str(tenant), str(user)]).encode()).hexdigest()


def brain_enabled() -> bool:
    return os.environ.get("GHOST_BRAIN_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


class UserMemory:
    """Tenant + user scoped view over the existing Tank memory corridor."""

    def __init__(self, memory, store):
        self.memory, self.store = memory, store
        self.state = BrainState(store)

    def is_off(self, tenant: str, user: str) -> bool:
        return bool(self.store.get_state(tenant, OFF_KEY + user, False))

    def set_off(self, tenant: str, user: str, off: bool) -> None:
        self.invalidate(tenant, user)
        self.store.set_state(tenant, OFF_KEY + user, bool(off))

    def epoch(self, tenant, user):
        return self.store.get_state(tenant, "memory_epoch:" + user, 0)

    def invalidate(self, tenant, user):
        self.store.set_state(tenant, "memory_epoch:" + user, self.epoch(tenant, user) + 1)
        self.state.invalidate(tenant, user)

    @staticmethod
    def _mine(row: dict, tenant: str, user: str) -> bool:
        # Rows come back from a shared tenant collection; treat their metadata as
        # untrusted. Every ownership field must match, or the row is not shown.
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        if row.get("tenant_id") is not None and str(row.get("tenant_id")) != str(tenant):
            return False
        return (row.get("source") == "autumbra" and row.get("kind") in KINDS
                and meta.get("product") == "autumbra" and meta.get("user_id") == user
                and meta.get("user_scope") == user_scope(tenant, user))

    async def list(self, tenant: str, user: str) -> list[dict]:
        # Hermes /records exposes SQL rows (claim/evidence), whereas recall
        # also supplies text/source. Normalize that documented wire difference.
        rows = [{**row, "text": row.get("text", row.get("claim", "")),
                 "source": row.get("source", next(iter(row.get("evidence") or []), ""))}
                for row in await self.memory.records(tenant, user_id=user)]
        return [row for row in rows if self._mine(row, tenant, user)]

    async def recall(self, tenant: str, user: str, query: str) -> list[dict]:
        if self.is_off(tenant, user):
            return []
        return [row for row in await self.memory.recall(tenant, query[:2000], limit=20, user_id=user) if self._mine(row, tenant, user)]

    async def remember(self, tenant: str, user: str, kind: str, text: str, *, key: str | None = None,
                       meta: dict | None = None, record_id: str | None = None,
                       evidence: list[str] | None = None, confidence: float = 1) -> dict | None:
        if kind not in KINDS:
            raise ValueError("Unknown memory kind.")
        if self.is_off(tenant, user):
            return None
        blob = text + " " + json.dumps(meta or {}, sort_keys=True, default=str)
        if contains_secret(blob):
            # Never store a secret; the caller keeps working without memory.
            return None
        return await self.memory.remember(
            tenant, text, kind, "autumbra", record_id=record_id, user_id=user,
            evidence=evidence or ["urn:autumbra:input:" + hashlib.sha256(text.encode()).hexdigest()], confidence=confidence,
            meta={**(meta or {}), "product": "autumbra", "user_id": user, "user_scope": user_scope(tenant, user),
                  **({"task_key": key} if key else {}), "memory_epoch": self.epoch(tenant, user)})

    async def edit(self, tenant: str, user: str, record_id: str, text: str) -> dict:
        if contains_secret(text):
            raise ValueError("Memory cannot hold secrets.")
        row = next((r for r in await self.list(tenant, user) if str(r.get("id")) == str(record_id)), None)
        if row is None:
            raise KeyError(record_id)
        meta = {k: v for k, v in (row.get("meta") or {}).items() if k not in {"product", "user_id", "user_scope"}}
        self.invalidate(tenant, user)
        return await self.memory.remember(tenant, text, row["kind"], "autumbra", record_id=str(record_id),
                                          user_id=user, replace=True, evidence=row.get("evidence") or [], confidence=1,
                                          meta={**meta, "product": "autumbra", "user_id": user,
                                                "user_scope": user_scope(tenant, user), "edited": True, "memory_epoch": self.epoch(tenant, user)})

    async def forget(self, tenant: str, user: str, record_id: str) -> None:
        if not any(str(r.get("id")) == str(record_id) for r in await self.list(tenant, user)):
            raise KeyError(record_id)
        self.invalidate(tenant, user)
        await self.memory.forget(record_id, tenant, user_id=user)


FreePass = Callable[[str, str], Awaitable[dict | None]]


class Brain:
    """Product brain bridge. ``service`` posts to the autumbra-brain service."""

    def __init__(self, memory: UserMemory, service: Callable[[dict, Any], Awaitable[dict]],
                 free_passes: list[FreePass] | None = None):
        self.memory, self.service, self.free_passes = memory, service, free_passes or []

    async def run(self, tenant: str, user: str | None, task_type: str, text: str,
                  run_id: str | None = None, *, actor=None) -> dict:
        tenant = str(uuid.UUID(tenant))
        if task_type not in TASK_TYPES or contains_secret(text):
            raise ValueError("Invalid Autumbra brain task.")
        task_id = str(uuid.UUID(run_id)) if run_id else str(uuid.uuid4())
        key = task_key(task_type, text)
        receipt: dict[str, Any] = {"tenant_id": tenant, "task_id": task_id, "user_id": user,
            "task_type": task_type, "cache_eligible": task_type in CACHE_ELIGIBLE,
            "steps": [], "model_receipts": [], "cost_usd": 0, "tokens_in": 0,
            "tokens_out": 0, "paid_calls": 0, "would_have_cost_usd": 0}
        # Default-off must precede ALL memory and checkpoint writes.
        if not brain_enabled():
            return {**receipt, "status": "paused", "answer": None, "source": "brain_off"}
        claimed, saved = self.memory.state.start(tenant, user or '', task_id, key)
        if not claimed:
            return {**(saved or receipt), "replayed": True,
                    **({"status": "pending", "answer": None} if saved is None else {})}
        active = bool(user) and not self.memory.is_off(tenant, user)
        receipt["memory_status"] = "available" if active else "off"
        receipt["memory_epoch"] = self.memory.epoch(tenant, user) if user else None
        recalled = []
        try:
            if active:
                recalled = await self.memory.recall(tenant, user, text)
                # Exact business repeat is SQL-backed; a vector top-k cannot hide it.
                owned = await self.memory.list(tenant, user)
                same = [r for r in owned if (r.get("meta") or {}).get("task_key") == key]
            else:
                same = []
        except RuntimeError as exc:
            if any(str(code) in str(exc) for code in (401, 403)):
                self.memory.state.save({**receipt, "status": "refused", "answer": None})
                raise PermissionError("Signed memory refused.") from None
            receipt["memory_status"] = "unavailable"
            same = []
        receipt["steps"].append({"action": "recall", "count": len(recalled)})
        same.sort(key=lambda r: (r.get("meta") or {}).get("memory_epoch", 0), reverse=True)
        correction = next((r for r in same if r.get("kind") == "correction"), None)
        previous = next((r for r in same if r.get("kind") == "outcome"
                         and (r.get("meta") or {}).get("memory_epoch") == self.memory.epoch(tenant, user)), None)
        if correction is not None:
            return await self._finish(receipt, user, key, correction["text"], "memory_correction", text)
        if previous is not None and task_type in CACHE_ELIGIBLE:
            receipt["would_have_cost_usd"] = (previous.get("meta") or {}).get("would_have_cost_usd", 0)
            return await self._finish(receipt, user, key, previous["text"], "memory_repeat", text)
        for free in self.free_passes:
            answer = await free(task_type, text)
            if answer:
                receipt["steps"].append({"action": "code_pass", "name": getattr(free, "__name__", "free")})
                return await self._finish(receipt, user, key, answer["answer"], "code", text)
        context = [{"kind": r.get("kind"), "text": r.get("text")} for r in recalled][:10]
        try:
            # The typed adapter scopes paid admission/cache by this unique run.
            # Exact business reuse and correction/forget/off stay above.
            result = await self.service({"tenant_id": tenant, "user_id": user, "task_id": task_id, "task_type": task_type,
                "text": text, "memory": context, "case_ref": user_scope(tenant, (user or '') + ':' + task_id),
                "home_region": os.environ.get("TANK_REGION", "us-east")}, actor)
            if result.get("tenant_id") != tenant or result.get("task_id") != task_id:
                raise RuntimeError("Brain receipt scope mismatch")
            if result.get("status") != "done":
                raise RuntimeError("Brain did not finish")
            receipt["model_receipts"] = list(result.get("model_receipts") or [])
            receipt["steps"].extend(result.get("steps") or [])
            return await self._finish(receipt, user, key, result["answer"], "brain", text)
        except (RuntimeError, ValueError, KeyError):
            # Uncertain payment never retries automatically, including after restart.
            failed = {**receipt, "status": "failed", "answer": None, "cost_usd": None,
                      "error": "Brain unavailable; this run will not be charged again."}
            self.memory.state.save(failed)
            return failed

    async def correct(self, tenant: str, user: str, task_type: str, text: str, corrected: str) -> dict | None:
        if task_type not in TASK_TYPES or not brain_enabled():
            raise ValueError("Autumbra brain is off or task type is invalid.")
        self.memory.invalidate(tenant, user)
        return await self.memory.remember(str(uuid.UUID(tenant)), user, "correction", corrected,
                                          key=task_key(task_type, text), meta={"task_type": task_type})

    async def _finish(self, receipt: dict, user: str | None, key: str, answer: str, source: str, text: str) -> dict:
        rows = receipt["model_receipts"]
        # Unknown billing is never reported as free.
        if any(r.get("cost_usd") is None or not r.get("ledger_id") for r in rows):
            raise RuntimeError("Incomplete Tank receipt")
        receipt.update(status="done", answer=answer, source=source,
                       cost_usd=round(sum(float(r["cost_usd"]) for r in rows), 8),
                       tokens_in=sum(int(r.get("tokens_in") or 0) for r in rows),
                       tokens_out=sum(int(r.get("tokens_out") or 0) for r in rows),
                       paid_calls=sum(1 for r in rows if float(r["cost_usd"]) > 0))
        if rows:
            receipt["would_have_cost_usd"] = sum(float(r.get("would_have_cost_usd", r["cost_usd"])) for r in rows)
        if contains_secret(answer):
            receipt.update(status="refused", answer=None, memory_status="refused")
            self.memory.state.save(receipt)
            return receipt
        # A concurrent forget/off/correction also invalidates an in-flight answer.
        if user and receipt["memory_epoch"] != self.memory.epoch(receipt["tenant_id"], user):
            receipt.update(status="invalidated", answer=None, memory_status="invalidated")
            self.memory.state.save(receipt)
            return receipt
        # Persist the paid result BEFORE attempting the fallible memory write.
        self.memory.state.save(receipt)
        if source in {"brain", "code"} and user and not self.memory.is_off(receipt["tenant_id"], user):
            try:
                await self.memory.remember(receipt["tenant_id"], user, "outcome", answer, key=key,
                    record_id=str(uuid.uuid5(uuid.NAMESPACE_URL, receipt["tenant_id"] + ':' + user + ':' + receipt["task_id"])),
                    evidence=["urn:tervory:ledger:" + str(r["ledger_id"]) for r in rows] or None,
                    confidence=0 if rows else 1, meta={
                        "task_type": receipt["task_type"], "task_id": receipt["task_id"], "source": source,
                        "input_hash": hashlib.sha256(text.encode()).hexdigest(),
                        "cost_usd": receipt["cost_usd"], "would_have_cost_usd": receipt["would_have_cost_usd"],
                        "tokens_in": receipt["tokens_in"], "tokens_out": receipt["tokens_out"]})
            except RuntimeError as exc:
                receipt["memory_status"] = "refused" if any(str(c) in str(exc) for c in (401, 403)) else "unavailable"
        receipt["steps"].append({"action": "remember", "source": source})
        self.memory.state.save(receipt)
        return receipt


async def classify_alert_code(task_type: str, text: str) -> dict | None:
    """Free code pass: existing message classifier answers clear alert words."""
    if task_type != "ghost.brain.classify_alert":
        return None
    lowered = (text or "").lower()
    if not any(word in lowered for word in ("slow", "latency", "captcha", "human check")):
        return None
    from .models import classify_message
    look = classify_message(text)
    return {"answer": f"{look.target.value}:{look.signal.value}"}
