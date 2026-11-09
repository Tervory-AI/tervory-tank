"""Gates 7+8 memory bracket for Base: recall before work, remember after.

Uses the product's existing memory client (ctx.memory / MemoryClient) only.
Tenant and user scope never cross. Secrets are refused. Corrections and prior
identical receipts recalled from memory are applied before any paid model call.
Missing authenticated user scope fails closed for memory (no tenant-as-user).
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Awaitable, Callable
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any

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

MEMORY_CONTROLS = frozenset({"off", "view", "edit", "forget"})


class MemoryControlError(PermissionError):
    """Raised when a memory control refuses an operation."""


class MemoryScopeError(ValueError):
    """Raised when authenticated user scope is missing for memory use."""


def _text_has_secret(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in FORBIDDEN_SECRET_MARKERS)


def memory_kinds() -> frozenset[str]:
    return frozenset(
        {
            "base.verified",
            "base.source",
            "base.failed_check",
            "base.quirk",
            "base.checkpoint",
            "base.correction",
            "base.receipt",
            "base.task",
        }
    )


def normalize_memory_control(value: Any) -> str:
    control = str(value or "edit").strip().lower()
    if control not in MEMORY_CONTROLS:
        raise ValueError(f"unsupported memory control: {control}")
    return control


def resolve_authenticated_user_id(cfg: dict[str, Any] | None, tenant_id: Any) -> str | None:
    """Return an authenticated user id, or None when memory must fail closed.

    Does not invent a shared tenant-as-user identity.
    """
    cfg = cfg or {}
    # Prefer explicit user_id; created_by is the Workspace session user on /v1/base/run.
    raw = cfg.get("user_id")
    if raw in (None, ""):
        raw = cfg.get("requested_by")
    if raw in (None, ""):
        raw = cfg.get("created_by")
    if raw in (None, ""):
        return None
    user = str(raw).strip()
    if not user:
        return None
    if user == str(tenant_id):
        # Synthetic shared identity — refuse for memory scope.
        return None
    return user


def require_authenticated_user_id(user_id: Any, *, tenant_id: Any = None) -> str:
    if user_id in (None, ""):
        raise MemoryScopeError("authenticated user_id required for Base memory")
    user = str(user_id).strip()
    if not user:
        raise MemoryScopeError("authenticated user_id required for Base memory")
    if tenant_id is not None and user == str(tenant_id):
        raise MemoryScopeError("tenant-as-user identity is refused for Base memory")
    return user


# Run/receipt identity — must not affect identical-reuse identity.
_RUN_OUT_OF_BAND_KEYS = frozenset(
    {
        "task_id",
        "run_id",
        "ledger_id",
        "request_id",
        "submission_hash",
        "memory_id",
        "id",
        "tenant_id",  # tenant already scoped separately; keep hash business-only
    }
)


def business_task_payload(task: dict[str, Any] | None) -> dict[str, Any]:
    """Business input only: drop run/receipt UUIDs and private underscore keys."""
    if not isinstance(task, dict):
        return {}
    out: dict[str, Any] = {}
    for key, value in task.items():
        name = str(key)
        if name in _RUN_OUT_OF_BAND_KEYS or name.startswith("_"):
            continue
        out[name] = value
    return out


def task_input_hash(task: dict[str, Any] | None) -> str:
    """Stable hash of business task input for identical-reuse identity.

    Fresh run/task/receipt UUIDs are out-of-band and must not change the hash.
    Meaningful business field changes must miss reuse.
    """
    payload = business_task_payload(task)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_memory_text(
    *,
    verified: list[str] | None = None,
    sources: list[str] | None = None,
    failed_checks: list[str] | None = None,
    quirks: list[str] | None = None,
    checkpoint: str | None = None,
    correction: str | None = None,
    receipt: str | None = None,
    summary: str | None = None,
) -> str:
    parts: list[str] = []
    if summary:
        parts.append(summary)
    if verified:
        parts.append("verified=" + ",".join(verified))
    if sources:
        parts.append("sources=" + ",".join(sources))
    if failed_checks:
        parts.append("failed_checks=" + ",".join(failed_checks))
    if quirks:
        parts.append("quirks=" + ",".join(quirks))
    if checkpoint:
        parts.append("checkpoint=" + checkpoint)
    if correction:
        parts.append("correction=" + correction)
    if receipt:
        parts.append("receipt=" + receipt)
    text = "; ".join(parts)
    if _text_has_secret(text):
        raise ValueError("Base memory refuses secret-bearing text")
    return text


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


def corrections_from_memories(rows: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    for row in rows:
        text = str(row.get("text", ""))
        corrected = (row.get("meta") or {}).get("correction")
        if isinstance(corrected, str) and corrected.strip():
            found.append(corrected.strip())
            continue
        marker = "correction="
        if marker in text:
            found.append(text.split(marker, 1)[1].split(";")[0].strip())
            continue
        if row.get("kind") == "base.correction" and text.strip():
            found.append(text.strip())
    return found


def identical_reuse_from_memories(
    rows: list[dict[str, Any]],
    *,
    task_key: str,
    input_hash: str,
) -> dict[str, Any] | None:
    """Prior identical receipt only when tenant+user scoped rows share task_key AND input hash.

    Caller must already filter tenant+user. Corrections are handled separately and
    override/invalidate stale identical results when present.
    """
    key = str(task_key)
    digest = str(input_hash)
    for row in reversed(rows):
        if row.get("kind") != "base.receipt":
            continue
        meta = row.get("meta") or {}
        if not isinstance(meta, dict):
            continue
        if str(meta.get("task_key", "")) != key:
            continue
        if str(meta.get("input_hash", "")) != digest:
            continue
        if meta.get("invalidated"):
            continue
        reusable = meta.get("reusable_result")
        if isinstance(reusable, dict) and reusable:
            return {
                "result": deepcopy(reusable),
                "memory_id": row.get("id"),
                "reuse": "identical_receipt",
                "input_hash": digest,
            }
    return None


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
    result["answered_from_memory"] = True
    return result


def _control_allows_recall(control: str) -> bool:
    return control in {"view", "edit", "forget"}


def _control_allows_remember(control: str) -> bool:
    return control in {"edit", "forget"}


def _control_allows_forget(control: str) -> bool:
    return control == "forget"


async def apply_memory_forget(
    memory: Any,
    *,
    memory_id: str,
    tenant_id: str,
    user_id: str,
    memory_control: str = "forget",
) -> None:
    """Explicit forget only. Never called from the task/brain paid path.

    Requires authenticated user_id and refuses cross-user deletes within a tenant.
    """
    control = normalize_memory_control(memory_control)
    if not _control_allows_forget(control):
        raise MemoryControlError(f"memory control {control!r} refuses forget")
    user = require_authenticated_user_id(user_id, tenant_id=tenant_id)
    tenant = str(tenant_id)
    # Ownership check before delete: list/recall then scope to this user.
    rows = []
    if hasattr(memory, "records"):
        rows = await memory.records(tenant, user_id=user)
    if not rows and hasattr(memory, "recall"):
        rows = await memory.recall(tenant, "", kind=None, limit=200, user_id=user)
    owned = [
        row
        for row in select_tenant_user_memories(rows, tenant_id=tenant, user_id=user)
        if str(row.get("id")) == str(memory_id)
    ]
    if not owned:
        # Fail closed: unknown or foreign memory id is not deleted.
        raise MemoryScopeError("forget refused: memory not in caller tenant+user scope")
    await memory.forget(memory_id, tenant, user_id=user)


async def run_with_memory(
    memory: Any,
    *,
    tenant_id: str,
    user_id: str,
    task_key: str,
    task: dict[str, Any],
    paid_call: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    memory_control: str = "edit",
) -> dict[str, Any]:
    """Product request → recall → correction | identical reuse | paid → remember.

    Returns a receipt with cost_usd / tokens for the run. Costs on the paid path
    must come from the paid_call (Tank receipts), not fabricated constants.
    """
    tenant = str(tenant_id)
    user = require_authenticated_user_id(user_id, tenant_id=tenant)
    control = normalize_memory_control(memory_control)

    receipt: dict[str, Any] = {
        "tenant_id": tenant,
        "user_id": user,
        "task_key": task_key,
        "memory_control": control,
        "steps": [],
        "cost_usd": 0.0,
        "tokens_in": 0,
        "tokens_out": 0,
        "paid_calls": 0,
        "answered_from_memory": False,
        "result": None,
    }

    if control == "off":
        receipt["input_hash"] = task_input_hash(task)
        receipt["steps"].append({"action": "memory_off"})
        paid = await paid_call(task)
        receipt["paid_calls"] = 1
        receipt.update(usage_from_model_receipts([paid]))
        receipt["result"] = paid.get("result", paid)
        receipt["steps"].append({"action": "brain_route", "status": "done"})
        return receipt

    if not _control_allows_recall(control):
        raise MemoryControlError(f"memory control {control!r} refuses recall")

    input_hash = task_input_hash(task)
    receipt["input_hash"] = input_hash

    recalled = await memory.recall(tenant, task_key, kind=None, limit=32, user_id=user)
    scoped = select_tenant_user_memories(recalled, tenant_id=tenant, user_id=user)
    receipt["steps"].append(
        {"action": "recall", "count": len(scoped), "memory_ids": [r["id"] for r in scoped]}
    )
    corrections = corrections_from_memories(scoped)

    if corrections:
        # Corrections override and invalidate stale identical receipts for this key.
        result = apply_corrections(task, corrections)
        receipt["answered_from_memory"] = True
        receipt["result"] = result
        receipt["steps"].append({"action": "apply_correction", "corrections": corrections})
        for row in scoped:
            meta = row.get("meta") or {}
            if (
                row.get("kind") == "base.receipt"
                and isinstance(meta, dict)
                and str(meta.get("task_key", "")) == str(task_key)
            ):
                meta["invalidated"] = True
                row["meta"] = meta
    else:
        identical = identical_reuse_from_memories(
            scoped, task_key=task_key, input_hash=input_hash
        )
        if identical is not None:
            # Short-circuit: paid_call (brain/Tank) is not invoked.
            receipt["answered_from_memory"] = True
            receipt["result"] = identical["result"]
            receipt["result"]["answered_from_memory"] = True
            receipt["result"]["reuse"] = "identical_receipt"
            receipt["steps"].append(
                {
                    "action": "identical_reuse",
                    "memory_id": identical.get("memory_id"),
                    "reuse": "identical_receipt",
                    "input_hash": input_hash,
                }
            )
        else:
            paid = await paid_call(task)
            receipt["paid_calls"] = 1
            # Usage must come from the paid brain/Tank path (receipts), not fixtures.
            receipt.update(usage_from_model_receipts([paid]))
            receipt["result"] = paid.get("result", paid)
            receipt["steps"].append({"action": "brain_route", "status": "done"})

    if receipt["answered_from_memory"]:
        return receipt

    if any(receipt[field] is None for field in ("cost_usd", "tokens_in", "tokens_out")):
        receipt["accounting_unknown"] = True
        receipt["steps"].append({"action": "remember_skipped", "reason": "accounting_unknown"})
        return receipt

    if not _control_allows_remember(control):
        receipt["steps"].append({"action": "remember_skipped", "reason": f"control:{control}"})
        return receipt

    text = build_memory_text(
        summary=f"Base task {task_key}: " + str((receipt["result"] or {}).get("summary") or ""),
        verified=list((receipt["result"] or {}).get("verified") or []) or None,
        sources=list((receipt["result"] or {}).get("sources") or []) or None,
        failed_checks=list((receipt["result"] or {}).get("failed_checks") or []) or None,
        quirks=list((receipt["result"] or {}).get("quirks") or []) or None,
        checkpoint=str((receipt["result"] or {}).get("checkpoint") or "") or None,
        correction=(receipt["result"] or {}).get("correction"),
        receipt=(
            f"cost={receipt['cost_usd']};tokens_in={receipt['tokens_in']};"
            f"tokens_out={receipt['tokens_out']}"
        ),
    )
    kind = "base.correction" if (receipt["result"] or {}).get("correction") else "base.receipt"
    meta = {
        "user_id": user,
        "task_key": task_key,
        "input_hash": input_hash,
        "reusable_result": deepcopy(receipt["result"] or {}),
    }
    # A newly stored correction invalidates prior identical receipts for this key.
    if kind == "base.correction":
        for row in memory.rows if hasattr(memory, "rows") else []:
            rmeta = row.get("meta") or {}
            if (
                row.get("tenant_id") == tenant
                and row.get("kind") == "base.receipt"
                and isinstance(rmeta, dict)
                and str(rmeta.get("user_id", "")) == user
                and str(rmeta.get("task_key", "")) == str(task_key)
            ):
                rmeta["invalidated"] = True
                row["meta"] = rmeta
        meta["reusable_result"] = None
    try:
        saved = await memory.remember(
            tenant, text, kind, f"base:task:{task_key}", meta=meta, user_id=user,
        )
    except (RuntimeError, TimeoutError, ConnectionError) as exc:
        # Keep the completed paid result; never dispatch it again after storage failure.
        # Chassis currently exposes these exact availability errors as RuntimeError.
        unavailable = isinstance(exc, (TimeoutError, ConnectionError)) or str(exc) in {
            "hermes unreachable", "hermes answered 502", "hermes answered 503", "hermes answered 504"}
        if not unavailable:
            raise
        receipt["memory_unavailable"] = True
        receipt["steps"].append({"action": "memory_unavailable", "status": "remember_failed"})
        return receipt
    receipt["steps"].append(
        {"action": "remember", "memory_id": saved["id"], "source": f"base:task:{task_key}"}
    )
    return receipt


def usage_from_model_receipts(rows: list[dict[str, Any]] | None) -> dict[str, float | int | None]:
    """Missing, malformed or unpriced accounting stays unknown, including empty ledgers."""
    def total(field: str, *, integer: bool = False):
        if not rows:
            return None
        amount = Decimal(0)
        for row in rows:
            if not isinstance(row, dict):
                return None
            raw = row.get(field)
            if raw is None or isinstance(raw, bool):
                return None
            if field == "cost_usd" and row.get("cost_status") not in (None, "set", "recorded", "reported"):
                return None
            try:
                value = Decimal(str(raw))
            except InvalidOperation:
                return None
            if not value.is_finite() or value < 0 or (integer and value != value.to_integral_value()):
                return None
            amount += value
        if integer:
            return int(amount)
        result = float(amount)
        return result if math.isfinite(result) else None

    cost = total("cost_usd")
    tokens_in = total("tokens_in", integer=True)
    tokens_out = total("tokens_out", integer=True)
    return {
        "cost_usd": cost,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tokens_total": tokens_in + tokens_out if tokens_in is not None and tokens_out is not None else None,
    }


async def product_to_brain_tank_memory(
    memory: Any,
    *,
    tenant_id: str,
    user_id: str,
    task_key: str,
    task: dict[str, Any],
    brain_tank_call: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    memory_control: str = "edit",
) -> dict[str, Any]:
    """Product → recall → (correction | identical reuse | brain→Tank→receipt) → remember.

    brain_tank_call must perform the real Base brain HTTP task and collect Tank
    /v1/agents/base/receipts, returning cost_usd, tokens_in, tokens_out, result.
    """
    return await run_with_memory(
        memory,
        tenant_id=tenant_id,
        user_id=user_id,
        task_key=task_key,
        task=task,
        paid_call=brain_tank_call,
        memory_control=memory_control,
    )
