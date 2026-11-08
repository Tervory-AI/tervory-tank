"""Gates 7+8 memory bracket for Rig: recall before work, remember after.

Uses the product's existing memory client (ctx.memory / MemoryClient) only.
Tenant and user scope never cross. Secrets are refused. Corrections recalled
from memory are applied before any paid model call. Exact repeats of the same
tenant+user+task_key+input hash return the approved outcome at $0 with no model
call.

What Rig remembers: past builds, store preferences, approved parts and fits,
quotes, rejected designs, corrections, receipts.
"""
from __future__ import annotations

import asyncio
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

# SETTING RIG_MEMORY_ENABLED — user can switch memory off; repeats then pay again.
# SETTING RIG_RECALL_TOKEN_BUDGET — fixed cap for summarised recall context.
DEFAULT_RECALL_TOKEN_BUDGET = 256
_RUN_KEYS = frozenset({"task_id", "run_id", "request_id"})


CACHE_ELIGIBLE_TASK_TYPES = frozenset(
    {
        "rig.ask",
        "rig.build",
        "rig.quote",
        "rig.fit",
        "build-repeat",
        "quote-repeat",
        "fit-repeat",
    }
)

MEMORY_OFF_KIND = "rig.setting"
MEMORY_OFF_SOURCE = "rig:memory:switch"
MEMORY_OFF_TEXT = "memory_off=true"


class MemoryScopeError(ValueError):
    """Tenant/user scope refused."""


class MemoryControlError(ValueError):
    """Memory control refuses the requested action."""


def refuse_auth_failure(exc: Exception) -> None:
    """The shipped MemoryClient exposes status only; auth is never an outage."""
    if isinstance(exc, (PermissionError, MemoryScopeError)) or str(exc) in {
        "hermes answered 401", "hermes answered 403",
    }:
        raise MemoryScopeError("Rig memory authorization refused") from None


def memory_enabled() -> bool:
    raw = os.environ.get("RIG_MEMORY_ENABLED", "false").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def recall_token_budget() -> int:
    raw = os.environ.get("RIG_RECALL_TOKEN_BUDGET", str(DEFAULT_RECALL_TOKEN_BUDGET)).strip()
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
            "rig.build",
            "rig.store_preference",
            "rig.part",
            "rig.fit",
            "rig.quote",
            "rig.rejected_design",
            "rig.correction",
            "rig.receipt",
            "rig.task",
            "rig.setting",
        }
    )


def require_authenticated_scope(*, tenant_id: Any, user_id: Any) -> tuple[str, str]:
    if tenant_id in (None, ""):
        raise MemoryScopeError("authenticated tenant_id required for Rig memory")
    tenant = str(tenant_id).strip()
    if not tenant:
        raise MemoryScopeError("authenticated tenant_id required for Rig memory")
    if user_id in (None, ""):
        raise MemoryScopeError("authenticated user_id required for Rig memory")
    user = str(user_id).strip()
    if not user:
        raise MemoryScopeError("authenticated user_id required for Rig memory")
    return tenant, user


def build_memory_text(
    *,
    past_builds: list[str] | None = None,
    store_preferences: list[str] | None = None,
    approved_parts: list[str] | None = None,
    approved_fits: list[str] | None = None,
    quotes: list[str] | None = None,
    rejected_designs: list[str] | None = None,
    correction: str | None = None,
    receipt: str | None = None,
    summary: str | None = None,
) -> str:
    parts: list[str] = []
    if summary:
        parts.append(summary)
    if past_builds:
        parts.append("builds=" + ",".join(past_builds))
    if store_preferences:
        parts.append("store_prefs=" + ",".join(store_preferences))
    if approved_parts:
        parts.append("parts=" + ",".join(approved_parts))
    if approved_fits:
        parts.append("fits=" + ",".join(approved_fits))
    if quotes:
        parts.append("quotes=" + ",".join(quotes))
    if rejected_designs:
        parts.append("rejected=" + ",".join(rejected_designs))
    if correction:
        parts.append("correction=" + correction)
    if receipt:
        parts.append("receipt=" + receipt)
    text = "; ".join(parts)
    if not text.strip():
        raise ValueError("Rig memory refuses empty remember text")
    if _text_has_secret(text):
        raise ValueError("Rig memory refuses secret-bearing text")
    return text


def memory_off_from_rows(rows: list[dict[str, Any]], *, tenant_id: str, user_id: str) -> bool:
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
    tenant = str(tenant_id)
    user = str(user_id)
    kept: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("tenant_id", "")) != tenant:
            continue
        meta = row.get("meta") or {}
        if not isinstance(meta, dict):
            continue
        owner = str(meta.get("user_id") or "")
        if owner != user and not (not owner and row.get("kind") == "rig.store_preference"):
            continue
        kept.append({**row, "text": row.get("text", row.get("claim", ""))})
    return kept


def task_input_fingerprint(task: dict[str, Any]) -> str:
    payload = {key: value for key, value in task.items() if key not in _RUN_KEYS}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def corrections_from_memories(rows: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    for row in rows:
        text = str(row.get("text", row.get("claim", "")))
        marker = "correction="
        if marker in text:
            found.append(text.split(marker, 1)[1].split(";")[0].strip())
            continue
        if row.get("kind") == "rig.correction" and text.strip():
            found.append(text.strip())
    return found


def apply_corrections(task: dict[str, Any], corrections: list[str]) -> dict[str, Any]:
    result = deepcopy(task)
    if not corrections:
        return result
    applied = list(result.get("applied_corrections") or [])
    for item in corrections:
        if item and item not in applied:
            applied.append(item)
    result["applied_corrections"] = applied
    result["answered_from_memory"] = True
    result["content"] = "; ".join(applied)
    return result


def approved_outcome_from_memories(
    rows: list[dict[str, Any]],
    *,
    task_key: str,
    input_fingerprint: str,
) -> dict[str, Any] | None:
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


def is_cache_eligible(task_key: str, task: dict[str, Any] | None = None) -> bool:
    del task
    return str(task_key) in CACHE_ELIGIBLE_TASK_TYPES


async def run_with_memory(
    memory: Any,
    *,
    tenant_id: str,
    user_id: str,
    task_key: str,
    task: dict[str, Any],
    paid_call: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    on_recall=None,
) -> dict[str, Any]:
    """Product request → recall → correction / exact repeat / brain/Tank → remember.

    Exact same tenant+user+task_key+input hash with an approved outcome returns
    from memory at $0 (receipt carries would_have_cost) before any paid call.

    Missing/invalid tenant or user raises MemoryScopeError (refused).
    Memory service outage answers without memory, marks receipt
    "memory unavailable", and never serves a stored repeat.
    """
    tenant, user = require_authenticated_scope(tenant_id=tenant_id, user_id=user_id)
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
        "memory_status": "ok",
    }

    async def _pay(reason: str, *, memory_status: str) -> dict[str, Any]:
        receipt["steps"].append({"action": "memory_bypass", "reason": reason})
        receipt["memory_status"] = memory_status
        if memory_status != "ok":
            receipt["memory_enabled"] = False
        paid = await paid_call(deepcopy(task))
        receipt["paid_calls"] = int(paid.get("paid_calls", 1))
        receipt["cost_usd"] = float(paid["cost_usd"]) if paid.get("cost_usd") is not None else None
        receipt["tokens_in"] = int(paid.get("tokens_in") or 0)
        receipt["tokens_out"] = int(paid.get("tokens_out") or 0)
        receipt["result"] = paid.get("result", paid)
        receipt["ledger_ids"] = paid.get("ledger_ids", [])
        if paid.get("ledger_id"):
            receipt["ledger_id"] = paid["ledger_id"]
        receipt["would_have_cost"] = {
            "cost_usd": receipt["cost_usd"],
            "tokens_in": receipt["tokens_in"],
            "tokens_out": receipt["tokens_out"],
        }
        receipt["steps"].append({"action": "brain_route", "status": "done"})
        return receipt

    if not memory_enabled():
        return await _pay("global", memory_status="off")

    try:
        setting_rows = await memory_call(memory.records(tenant, user_id=user))
    except Exception as exc:
        refuse_auth_failure(exc)
        # Service outage on settings read: continue without memory, never repeat.
        paid_receipt = await _pay("records_outage", memory_status="memory unavailable")
        return paid_receipt
    if memory_off_from_rows(setting_rows, tenant_id=tenant, user_id=user):
        return await _pay("per_user", memory_status="off")

    try:
        # Pass verified actor user_id; Hermes scopes — no product filter.
        recalled = await memory_call(memory.recall(tenant, task_key, kind=None, limit=32, user_id=user))
    except Exception as exc:
        refuse_auth_failure(exc)
        return await _pay("recall_outage", memory_status="memory unavailable")

    for row in recalled:
        owner = (row.get("meta") or {}).get("user_id")
        if str(row.get("tenant_id")) != tenant or (owner != user and not (
                not owner and row.get("kind") == "rig.store_preference")):
            raise MemoryScopeError("Memory response scope mismatch")
    if on_recall is not None:
        await on_recall(len(recalled))
    corrections = corrections_from_memories([r for r in recalled if (r.get("meta") or {}).get("task_key") == task_key and (r.get("meta") or {}).get("input_fingerprint", fingerprint) == fingerprint])
    approved = approved_outcome_from_memories(
        recalled, task_key=task_key, input_fingerprint=fingerprint
    )
    receipt["steps"].append(
        {"action": "recall", "count": len(recalled), "memory_ids": [r.get("id") for r in recalled]}
    )

    if corrections:
        result = apply_corrections(task, corrections)
        receipt["answered_from_memory"] = True
        receipt["result"] = result
        receipt["steps"].append({"action": "apply_correction", "corrections": corrections})
    elif approved is not None and is_cache_eligible(task_key, task):
        result = deepcopy(approved["outcome"])
        result["answered_from_memory"] = True
        receipt["answered_from_memory"] = True
        receipt["result"] = result
        receipt["would_have_cost"] = approved["would_have_cost"]
        receipt["paid_calls"] = 0
        receipt["cost_usd"] = 0.0
        receipt["tokens_in"] = 0
        receipt["tokens_out"] = 0
        receipt["steps"].append(
            {
                "action": "exact_repeat_from_memory",
                "memory_id": approved.get("memory_id"),
                "would_have_cost": approved["would_have_cost"],
            }
        )
    else:
        work = deepcopy(task)
        remaining = DEFAULT_RECALL_TOKEN_BUDGET * 4
        work["memories"] = []
        for row in recalled:
            text = str(row.get("text", row.get("claim", "")))[:remaining]
            if text:
                work["memories"].append({"id": row["id"], "kind": row.get("kind"), "text": text})
                remaining -= len(text)
        paid = await paid_call(work)
        receipt["paid_calls"] = int(paid.get("paid_calls", 1))
        receipt["cost_usd"] = float(paid["cost_usd"]) if paid.get("cost_usd") is not None else None
        receipt["tokens_in"] = int(paid.get("tokens_in") or 0)
        receipt["tokens_out"] = int(paid.get("tokens_out") or 0)
        receipt["result"] = paid.get("result", paid)
        receipt["ledger_ids"] = paid.get("ledger_ids", [])
        if paid.get("ledger_id"):
            receipt["ledger_id"] = paid["ledger_id"]
        receipt["would_have_cost"] = {
            "cost_usd": receipt["cost_usd"],
            "tokens_in": receipt["tokens_in"],
            "tokens_out": receipt["tokens_out"],
        }
        receipt["steps"].append({"action": "brain_route", "status": "done"})

    if receipt.get("memory_status") == "memory unavailable":
        return receipt

    result_obj = receipt["result"] or {}
    try:
        text_body = build_memory_text(
            summary=str(result_obj.get("content") or result_obj.get("summary") or f"Rig task {task_key}")[:1000],
            past_builds=list(result_obj.get("past_builds") or result_obj.get("builds") or []) or None,
            store_preferences=list(result_obj.get("store_preferences") or []) or None,
            approved_parts=list(result_obj.get("approved_parts") or result_obj.get("parts") or []) or None,
            approved_fits=list(result_obj.get("approved_fits") or result_obj.get("fits") or []) or None,
            quotes=list(result_obj.get("quotes") or []) or None,
            rejected_designs=list(result_obj.get("rejected_designs") or []) or None,
            correction=result_obj.get("correction"),
            receipt=(
                f"cost={receipt['cost_usd']};tokens_in={receipt['tokens_in']};"
                f"tokens_out={receipt['tokens_out']}"
            ),
        )
        kind = "rig.correction" if result_obj.get("correction") else "rig.receipt"
        would = receipt.get("would_have_cost") or {
            "cost_usd": receipt["cost_usd"],
            "tokens_in": receipt["tokens_in"],
            "tokens_out": receipt["tokens_out"],
        }
        approved_flag = (receipt["paid_calls"] >= 1 and receipt["cost_usd"] is not None) or bool(result_obj.get("answered_from_memory"))
        outcome_to_store = deepcopy(result_obj)
        saved = await memory_call(memory.remember(
            tenant,
            text_body,
            kind,
            f"rig:task:{task_key}",
            user_id=user,
            meta={
                "user_id": user,
                "task_key": task_key,
                "input_fingerprint": fingerprint,
                "approved": approved_flag and not result_obj.get("correction"),
                "outcome": outcome_to_store if approved_flag and not result_obj.get("correction") else None,
                "would_have_cost": would,
            },
        ))
        receipt["steps"].append({"action": "remember", "memory_id": saved["id"], "source": f"rig:task:{task_key}"})
    except Exception as exc:
        refuse_auth_failure(exc)
        receipt["steps"].append({"action": "remember_failed", "status": "memory unavailable"})
        if receipt["memory_status"] == "ok":
            receipt["memory_status"] = "memory unavailable"
    return receipt


async def memory_call(operation):
    """Bound each shared client operation, including a stalled transport."""
    return await asyncio.wait_for(operation, timeout=60)
