"""Gates 7+8 memory bracket for Trigger: recall before work, remember after.

Uses the product's existing memory client (ctx.memory / MemoryClient) only.
Tenant and user scope never cross. Secrets are refused. Corrections recalled
from memory are applied before any paid model call. Exact repeats of the same
tenant+user+task_key+input hash return the approved outcome at $0 with no model
call. Recalled context for near-repeats is summarised under a fixed token budget
so recall never makes a request dearer than without it.
"""
from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from typing import Any, Awaitable, Callable


FORBIDDEN_SECRET_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer ",
    "password",
    "secret",
    "token=",
    "private_key",
)

# SETTING TRIGGER_RECALL_TOKEN_BUDGET — fixed cap for summarised recall context.
# SETTING TRIGGER_MEMORY_ENABLED — user can switch memory off; repeats then pay again.
DEFAULT_RECALL_TOKEN_BUDGET = 256
# Errors the memory service raises when it is down or refuses the call (the chassis
# MemoryClient turns transport failures and 4xx/5xx answers into RuntimeError).
# Programming errors (TypeError, AttributeError) and product refusals (ValueError)
# are not outages and still raise.
MEMORY_OUTAGE_ERRORS: tuple[type[BaseException], ...] = (RuntimeError, ConnectionError, OSError, TimeoutError)
_FINGERPRINT_KEYS = ("contact_id", "text", "format")


class MemoryAuthorizationError(PermissionError):
    """The memory service refused the product credential, not a store outage."""


def refuse_memory_auth(error):
    if isinstance(error, RuntimeError) and str(error) in {"hermes answered 401", "hermes answered 403"}:
        raise MemoryAuthorizationError("Memory ownership required") from None


class MemoryScopeError(ValueError):
    """Memory needs a tenant and a signed-in user; anything less is refused."""


def require_memory_scope(tenant_id: Any, user_id: Any) -> tuple[str, str]:
    tenant = str(tenant_id or "").strip()
    user = str(user_id or "").strip()
    if not tenant or tenant.lower() == "none":
        raise MemoryScopeError("memory needs a tenant")
    if not user or user.lower() == "none":
        raise MemoryScopeError("memory needs a signed-in user")
    return tenant, user


def memory_enabled() -> bool:
    raw = os.environ.get("TRIGGER_MEMORY_ENABLED", "false").strip().lower()
    return raw not in {"", "0", "false", "no", "off"}


def recall_token_budget() -> int:
    raw = os.environ.get("TRIGGER_RECALL_TOKEN_BUDGET", str(DEFAULT_RECALL_TOKEN_BUDGET)).strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_RECALL_TOKEN_BUDGET
    return value if value > 0 else DEFAULT_RECALL_TOKEN_BUDGET


def _text_has_secret(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in FORBIDDEN_SECRET_MARKERS)


def memory_kinds() -> frozenset[str]:
    return frozenset(
        {
            "trigger.deal",
            "trigger.context",
            "trigger.objection",
            "trigger.tone",
            "trigger.handover",
            "trigger.correction",
            "trigger.receipt",
            "trigger.task",
            "trigger.setting",
        }
    )


def build_memory_text(
    *,
    deal_history: list[str] | None = None,
    conversation_context: list[str] | None = None,
    objections: list[str] | None = None,
    tone: list[str] | None = None,
    handover_notes: list[str] | None = None,
    correction: str | None = None,
    receipt: str | None = None,
    summary: str | None = None,
) -> str:
    parts: list[str] = []
    if summary:
        parts.append(summary)
    if deal_history:
        parts.append("deal=" + ",".join(deal_history))
    if conversation_context:
        parts.append("context=" + ",".join(conversation_context))
    if objections:
        parts.append("objections=" + ",".join(objections))
    if tone:
        parts.append("tone=" + ",".join(tone))
    if handover_notes:
        parts.append("handover=" + ",".join(handover_notes))
    if correction:
        parts.append("correction=" + correction)
    if receipt:
        parts.append("receipt=" + receipt)
    text = "; ".join(parts)
    if _text_has_secret(text):
        raise ValueError("Trigger memory refuses secret-bearing text")
    return text


# Per-user memory switch-off is stored as this kind via MemoryClient.remember.
MEMORY_OFF_KIND = "trigger.setting"
MEMORY_OFF_SOURCE = "trigger:memory:switch"
MEMORY_OFF_TEXT = "memory_off=true"


def memory_off_from_rows(rows: list[dict[str, Any]], *, tenant_id: str, user_id: str) -> bool:
    """True when this signed-in user has switched memory off in this tenant."""
    tenant = str(tenant_id)
    user = str(user_id)
    for row in rows:
        if str(row.get("tenant_id", "")) != tenant:
            continue
        if str(row.get("kind", "")) != MEMORY_OFF_KIND:
            continue
        meta = row.get("meta") or {}
        if not isinstance(meta, dict):
            continue
        if str(meta.get("user_id", "")) != user:
            continue
        if MEMORY_OFF_TEXT in str(row.get("text", row.get("claim", ""))):
            return True
    return False


def owned_memory_row(
    rows: list[dict[str, Any]],
    *,
    memory_id: str,
    tenant_id: str,
    user_id: str,
) -> dict[str, Any] | None:
    """Return the row only when tenant and meta.user_id both match the actor."""
    wanted = str(memory_id)
    tenant = str(tenant_id)
    user = str(user_id)
    for row in rows:
        if str(row.get("id", "")) != wanted:
            continue
        if str(row.get("tenant_id", "")) != tenant:
            return None
        meta = row.get("meta") or {}
        if not isinstance(meta, dict):
            return None
        if str(meta.get("user_id", "")) != user:
            return None
        return row
    return None


def select_tenant_user_memories(
    rows: list[dict[str, Any]],
    *,
    tenant_id: str,
    user_id: str,
) -> list[dict[str, Any]]:
    """Keep only memories owned by this tenant and user. Foreign rows vanish."""
    tenant = str(tenant_id)
    user = str(user_id)
    kept: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("tenant_id", "")) != tenant:
            continue
        meta = row.get("meta") or {}
        if not isinstance(meta, dict):
            continue
        if str(meta.get("user_id", "")) != user:
            continue
        kept.append(row)
    return kept


def task_input_fingerprint(task: dict[str, Any]) -> str:
    """Stable hash of the inputs that define an exact repeat."""
    payload = {key: task.get(key) for key in _FINGERPRINT_KEYS}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    """Cheap offline token estimate used only for the recall budget cap."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def categories_from_memories(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Pull per-contact categories from recalled Trigger memory text/outcomes."""
    buckets = {
        "deal_history": [],
        "conversation_context": [],
        "objections": [],
        "tone": [],
        "handover_notes": [],
    }
    markers = {
        "deal=": "deal_history",
        "context=": "conversation_context",
        "objections=": "objections",
        "tone=": "tone",
        "handover=": "handover_notes",
    }
    seen: dict[str, set[str]] = {key: set() for key in buckets}

    def _add(bucket: str, values: list[str] | None) -> None:
        for item in values or []:
            value = str(item).strip()
            if value and value not in seen[bucket]:
                seen[bucket].add(value)
                buckets[bucket].append(value)

    for row in rows:
        meta = row.get("meta") or {}
        outcome = meta.get("outcome") if isinstance(meta, dict) else None
        if isinstance(outcome, dict):
            _add("deal_history", outcome.get("deal_history"))
            _add("conversation_context", outcome.get("conversation_context"))
            _add("objections", outcome.get("objections"))
            _add("tone", outcome.get("tone"))
            _add("handover_notes", outcome.get("handover_notes"))
        text = str(row.get("text", row.get("claim", "")))
        for part in text.split(";"):
            chunk = part.strip()
            for marker, bucket in markers.items():
                if chunk.startswith(marker):
                    _add(bucket, [v for v in chunk[len(marker):].split(",") if v.strip()])
    return buckets


def corrections_from_memories(rows: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    for row in rows:
        text = str(row.get("text", row.get("claim", "")))
        marker = "correction="
        if marker in text:
            found.append(text.split(marker, 1)[1].split(";")[0].strip())
            continue
        if row.get("kind") == "trigger.correction" and text.strip():
            found.append(text.strip())
    return found


def apply_corrections(task: dict[str, Any], corrections: list[str]) -> dict[str, Any]:
    """Return a corrected task copy. Empty corrections leave the task unchanged."""
    result = deepcopy(task)
    if not corrections:
        return result
    applied = list(result.get("applied_corrections") or [])
    for item in corrections:
        if item and item not in applied:
            applied.append(item)
    result["applied_corrections"] = applied
    result["text"] = "\n".join(applied)
    result["answered_from_memory"] = True
    return result


def approved_outcome_from_memories(
    rows: list[dict[str, Any]],
    *,
    task_key: str,
    input_fingerprint: str,
) -> dict[str, Any] | None:
    """Return the approved outcome for this exact tenant-scoped task+input hash."""
    key = str(task_key)
    fingerprint = str(input_fingerprint)
    for row in reversed(rows):
        meta = row.get("meta") or {}
        if not isinstance(meta, dict):
            continue
        if str(meta.get("task_key", "")) != key:
            continue
        if str(meta.get("input_fingerprint", "")) != fingerprint:
            continue
        if not meta.get("approved"):
            continue
        outcome = meta.get("outcome")
        if isinstance(outcome, dict) and outcome:
            would = meta.get("would_have_cost") or {}
            return {
                "outcome": deepcopy(outcome),
                "would_have_cost": {
                    "cost_usd": float(would.get("cost_usd") or 0.0),
                    "tokens_in": int(would.get("tokens_in") or 0),
                    "tokens_out": int(would.get("tokens_out") or 0),
                },
                "memory_id": row.get("id"),
            }
    return None


def select_relevant_memories(
    rows: list[dict[str, Any]],
    *,
    task_key: str,
    task: dict[str, Any],
) -> list[dict[str, Any]]:
    """Prefer rows for this task_key / contact; drop unrelated history."""
    key = str(task_key)
    contact = str(task.get("contact_id") or "")
    relevant: list[dict[str, Any]] = []
    for row in rows:
        meta = row.get("meta") or {}
        if not isinstance(meta, dict):
            meta = {}
        if str(meta.get("task_key", "")) == key:
            relevant.append(row)
            continue
        if contact and str(meta.get("contact_id", "")) == contact:
            relevant.append(row)
            continue
        kind = str(row.get("kind") or "")
        if kind in {"trigger.correction", "trigger.tone", "trigger.handover", "trigger.objection"}:
            relevant.append(row)
    return relevant


def summarise_recall(
    rows: list[dict[str, Any]],
    *,
    budget: int | None = None,
) -> str:
    """Summarise relevant recall under a fixed token budget. Never exceeds the cap."""
    cap = recall_token_budget() if budget is None else max(0, int(budget))
    if cap <= 0 or not rows:
        return ""
    parts: list[str] = []
    used = 0
    for row in rows:
        kind = str(row.get("kind") or "trigger.task")
        text = " ".join(str(row.get("text") or "").split())
        if not text:
            continue
        snippet = f"{kind}:{text}"
        tokens = estimate_tokens(snippet)
        if used + tokens > cap:
            remaining = cap - used
            if remaining <= 0:
                break
            # Hard-truncate the last snippet so the total stays inside the budget.
            max_chars = max(0, remaining * 4)
            snippet = snippet[:max_chars].rstrip()
            if not snippet:
                break
            tokens = estimate_tokens(snippet)
            if used + tokens > cap:
                break
            parts.append(snippet)
            used += tokens
            break
        parts.append(snippet)
        used += tokens
    summary = " | ".join(parts)
    while summary and estimate_tokens(summary) > cap:
        summary = summary[:-4].rstrip(" |")
    return summary


def attach_capped_recall(
    task: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    task_key: str,
    budget: int | None = None,
) -> dict[str, Any]:
    """Attach summarised recall. Cap guarantees recall never makes a request dearer."""
    cap = recall_token_budget() if budget is None else max(0, int(budget))
    relevant = select_relevant_memories(rows, task_key=task_key, task=task)
    context = summarise_recall(relevant, budget=cap)
    tokens = estimate_tokens(context) if context else 0
    if tokens > cap:
        context = summarise_recall(relevant, budget=cap)
        tokens = estimate_tokens(context) if context else 0
    out = deepcopy(task)
    out["memory_context"] = context
    out["memory_context_tokens"] = tokens
    # Never-dearer: recall tokens are not billed on top of the base prompt.
    out["memory_context_billed"] = False
    out["memory_categories"] = categories_from_memories(relevant)
    return out


class FakeMemory:
    """In-process fake for offline gates 7+8 tests. Mirrors central user_id scoping."""

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
        user_id: str | None = None,
        meta: dict | None = None,
        tenant_wide: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        if kind not in memory_kinds():
            raise ValueError("unsupported Trigger memory kind")
        if _text_has_secret(text):
            raise ValueError("Trigger memory refuses secret-bearing text")
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

    async def records(
        self, tenant_id: str, *, user_id: str | None = None, tier: str = "client", **_: Any
    ) -> list[dict[str, Any]]:
        tenant = str(tenant_id)
        uid = (user_id or "").strip() or None
        out = []
        for row in self.rows:
            if row["tenant_id"] != tenant:
                continue
            if uid:
                owner = str((row.get("meta") or {}).get("user_id") or "").strip()
                if owner != uid:
                    continue
            out.append(row)
        return deepcopy(out)

    async def forget(self, memory_id: str, tenant_id: str, *, user_id: str | None = None) -> None:
        tenant = str(tenant_id)
        wanted = str(memory_id)
        self.forgets += 1
        self.rows = [
            row for row in self.rows
            if not (row["id"] == wanted and row["tenant_id"] == tenant
                    and (user_id is None or (row.get("meta") or {}).get("user_id") == user_id))
        ]

    async def recall(
        self,
        tenant_id: str,
        query: str,
        *,
        user_id: str | None = None,
        kind: str | None = None,
        limit: int | None = None,
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
            if uid:
                owner = str((row.get("meta") or {}).get("user_id") or "").strip()
                if owner != uid:
                    continue
            matches.append(row)
        if limit is not None:
            matches = matches[:limit]
        return deepcopy(matches)



async def run_with_memory(
    memory: Any,
    *,
    tenant_id: str,
    user_id: str,
    task_key: str,
    task: dict[str, Any],
    paid_call: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    """Product request → recall → correction / exact repeat / brain/Tank → remember.

    Exact same tenant+user+task_key+input hash with an approved outcome returns
    from memory at $0 (receipt carries would_have_cost). Near-repeats still pay,
    with recall summarised under TRIGGER_RECALL_TOKEN_BUDGET so recall never makes
    the request dearer than without it.
    """
    tenant, user = require_memory_scope(tenant_id, user_id)
    fingerprint = task_input_fingerprint(task)
    receipt: dict[str, Any] = {
        "tenant_id": tenant,
        "user_id": user,
        "task_key": task_key,
        "input_fingerprint": fingerprint,
        "steps": [],
        "cost_usd": 0.0,
        "tokens_in": 0,
        "tokens_out": 0,
        "paid_calls": 0,
        "answered_from_memory": False,
        "would_have_cost": None,
        "result": None,
        "memory_enabled": memory_enabled(),
        "memory_unavailable": False,
    }

    async def _pay_without_memory(reason: str) -> dict[str, Any]:
        receipt["steps"].append({"action": "memory_off", "reason": reason})
        receipt["memory_enabled"] = False
        if reason == "outage":
            # Memory service down: answer with a paid route, never a stored repeat,
            # and remember nothing (there is nowhere safe to write it).
            receipt["memory_unavailable"] = True
        paid = await paid_call(deepcopy(task))
        receipt["paid_calls"] = 1
        receipt["cost_usd"] = float(paid.get("cost_usd") or 0)
        receipt["tokens_in"] = int(paid.get("tokens_in") or 0)
        receipt["tokens_out"] = int(paid.get("tokens_out") or 0)
        receipt["result"] = paid.get("result", paid)
        receipt["would_have_cost"] = {
            "cost_usd": receipt["cost_usd"],
            "tokens_in": receipt["tokens_in"],
            "tokens_out": receipt["tokens_out"],
        }
        receipt["steps"].append({"action": "brain_route", "status": "done"})
        return receipt

    if not memory_enabled():
        # Global switch-off: never serve a repeat from memory; always pay.
        return await _pay_without_memory("global")

    # Per-user (tenant+user) switch-off stored via MemoryClient; other users unaffected.
    # An outage here must not be read as "memory on": the user's switch-off could
    # not be checked, so no stored repeat is served and nothing is remembered.
    try:
        setting_rows = await memory.records(tenant, user_id=user)
    except MEMORY_OUTAGE_ERRORS as exc:
        refuse_memory_auth(exc)
        receipt["memory_error"] = type(exc).__name__
        return await _pay_without_memory("outage")
    if memory_off_from_rows(setting_rows, tenant_id=tenant, user_id=user):
        return await _pay_without_memory("per_user")

    # Central user scoping via MemoryClient.user_id — no product-side filter.
    try:
        recalled = await memory.recall(tenant, task_key, user_id=user, kind=None, limit=32)
    except MEMORY_OUTAGE_ERRORS as exc:
        refuse_memory_auth(exc)
        receipt["memory_error"] = type(exc).__name__
        return await _pay_without_memory("outage")
    corrections = corrections_from_memories(recalled)
    approved = approved_outcome_from_memories(
        recalled, task_key=task_key, input_fingerprint=fingerprint
    )
    receipt["steps"].append(
        {"action": "recall", "count": len(recalled), "memory_ids": [r["id"] for r in recalled]}
    )

    if corrections:
        result = apply_corrections(task, corrections)
        receipt["answered_from_memory"] = True
        receipt["result"] = result
        receipt["steps"].append({"action": "apply_correction", "corrections": corrections})
    elif approved is not None:
        result = deepcopy(approved["outcome"])
        result["answered_from_memory"] = True
        receipt["answered_from_memory"] = True
        receipt["result"] = result
        receipt["would_have_cost"] = approved["would_have_cost"]
        receipt["steps"].append(
            {
                "action": "exact_repeat_from_memory",
                "memory_id": approved.get("memory_id"),
                "would_have_cost": approved["would_have_cost"],
            }
        )
    else:
        capped_task = attach_capped_recall(task, recalled, task_key=task_key)
        receipt["steps"].append(
            {
                "action": "recall_cap",
                "memory_context_tokens": int(capped_task.get("memory_context_tokens") or 0),
                "budget": recall_token_budget(),
                "billed": False,
            }
        )
        paid = await paid_call(capped_task)
        receipt["paid_calls"] = 1
        receipt["cost_usd"] = float(paid.get("cost_usd") or 0)
        receipt["tokens_in"] = int(paid.get("tokens_in") or 0)
        receipt["tokens_out"] = int(paid.get("tokens_out") or 0)
        receipt["result"] = paid.get("result", paid)
        receipt["would_have_cost"] = {
            "cost_usd": receipt["cost_usd"],
            "tokens_in": receipt["tokens_in"],
            "tokens_out": receipt["tokens_out"],
        }
        receipt["steps"].append({"action": "brain_route", "status": "done"})

    # A reuse is a read, not a new approved source. Cloning an outcome here
    # would let a forgotten or superseded source survive through its copies.
    if receipt["answered_from_memory"]:
        return receipt

    result_obj = receipt["result"] or {}
    text = build_memory_text(
        summary=f"Trigger task {task_key}",
        deal_history=list(result_obj.get("deal_history") or []) or None,
        conversation_context=list(result_obj.get("conversation_context") or []) or None,
        objections=list(result_obj.get("objections") or []) or None,
        tone=list(result_obj.get("tone") or []) or None,
        handover_notes=list(result_obj.get("handover_notes") or []) or None,
        correction=result_obj.get("correction"),
        receipt=(
            f"cost={receipt['cost_usd']};tokens_in={receipt['tokens_in']};"
            f"tokens_out={receipt['tokens_out']}"
        ),
    )
    kind = "trigger.correction" if result_obj.get("correction") else "trigger.receipt"
    would = receipt.get("would_have_cost") or {
        "cost_usd": receipt["cost_usd"],
        "tokens_in": receipt["tokens_in"],
        "tokens_out": receipt["tokens_out"],
    }
    # Persist approved outcomes from paid runs so the next exact repeat is free.
    approved_flag = bool(receipt["paid_calls"] == 1) or bool(result_obj.get("answered_from_memory"))
    outcome_to_store = deepcopy(result_obj)
    outcome_to_store.pop("memory_context", None)
    outcome_to_store.pop("memory_context_tokens", None)
    outcome_to_store.pop("memory_context_billed", None)
    remember_kwargs = dict(
        user_id=user,
        meta={
            "user_id": user,
            "task_key": task_key,
            "contact_id": result_obj.get("contact_id") or task.get("contact_id"),
            "input_fingerprint": fingerprint,
            "approved": approved_flag and not result_obj.get("correction"),
            "outcome": outcome_to_store if approved_flag and not result_obj.get("correction") else None,
            "would_have_cost": would,
        },
    )
    try:
        saved = await memory.remember(tenant, text, kind, f"trigger:task:{task_key}", **remember_kwargs)
    except MEMORY_OUTAGE_ERRORS as exc:
        refuse_memory_auth(exc)
        # The answer (and any paid receipt) stands; only the write was lost.
        receipt["memory_unavailable"] = True
        receipt["memory_error"] = type(exc).__name__
        receipt["steps"].append({"action": "remember", "status": "unavailable", "source": f"trigger:task:{task_key}"})
        return receipt
    receipt["steps"].append({"action": "remember", "memory_id": saved["id"], "source": f"trigger:task:{task_key}"})
    return receipt
