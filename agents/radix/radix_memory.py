"""Gates 7+8 memory bracket for Radix: recall before work, remember after.

Uses the product's existing memory client (ctx.memory / MemoryClient) only.
Tenant and user scope never cross. Secrets are refused. Corrections and prior
identical receipts recalled from memory are applied before any paid brain or
Tank route.

What Radix remembers: sites scanned, past findings and fixes, accepted risks,
false positives marked — every remembered field carries a real value.

View / edit / forget / switch-off are per tenant+user via MemoryClient. The
authenticated actor must match the target record's tenant AND user or the call
is refused before any read or mutation. Per-user OFF is stored in memory, not
a global env flip.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Awaitable, Callable

FORBIDDEN_SECRET_MARKERS = (
    "api_key", "apikey", "authorization", "bearer ", "password",
    "secret", "token=", "private_key",
)

MEMORY_CONTROLS = frozenset({"off", "view", "edit", "forget"})
CONTROL_KIND = "radix.memory_control"
CONTROL_SOURCE = "radix:memory_control"

# t51: only these kinds may omit meta.user_id (tenant-wide). All other Radix
# kinds are personal and require the verified actor user_id. Products do NOT
# filter users themselves — they only pass Actor.user_id into the shared client.
TENANT_WIDE_KINDS: frozenset[str] = frozenset()


CACHE_ELIGIBLE_TASK_TYPES = frozenset({
    "radix.site_risk",
    "radix.verify_business",
    "radix.business_risk",
    "radix.account_links",
    "radix.entity_links",
    "scan-site",
    "scan-repeat",
    "scan-cost-twice",
    "scan-source-retry",
})


class MemoryScopeError(ValueError):
    """Tenant/user scope refused."""

class MemoryUnavailableError(RuntimeError):
    """Hermes outage or unreachable — product answers without memory."""


def is_memory_outage(exc: BaseException) -> bool:
    import httpx
    import asyncio
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    if isinstance(exc, (httpx.TransportError, asyncio.TimeoutError, ConnectionError)):
        return True
    if isinstance(exc, MemoryUnavailableError):
        return True
    text = str(exc).lower()
    if any(code in text for code in ("401", "403", "scope", "signed user")):
        return False
    markers = (
        "hermes answered 503",
        "memory store unreachable",
        "connection refused",
        "connect error",
        "timed out",
        "timeout",
        "unreachable",
        "memory unavailable",
    )
    return any(m in text for m in markers)



class MemoryControlError(ValueError):
    """Memory control refuses the requested action."""


def _text_has_secret(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in FORBIDDEN_SECRET_MARKERS)


def memory_kinds() -> frozenset[str]:
    return frozenset({
        "radix.site_scan",
        "radix.finding",
        "radix.fix",
        "radix.accepted_risk",
        "radix.false_positive",
        "radix.correction",
        "radix.receipt",
        "radix.task",
        CONTROL_KIND,
    })


def normalize_memory_control(value: Any) -> str:
    control = str(value or "edit").strip().lower()
    if control not in MEMORY_CONTROLS:
        raise ValueError(f"unsupported memory control: {control}")
    return control


def require_authenticated_scope(*, tenant_id: Any, user_id: Any) -> tuple[str, str]:
    if tenant_id in (None, ""):
        raise MemoryScopeError("authenticated tenant_id required for Radix memory")
    tenant = str(tenant_id).strip()
    if not tenant:
        raise MemoryScopeError("authenticated tenant_id required for Radix memory")
    if user_id in (None, ""):
        raise MemoryScopeError("authenticated user_id required for Radix memory")
    user = str(user_id).strip()
    if not user:
        raise MemoryScopeError("authenticated user_id required for Radix memory")
    if user == tenant:
        raise MemoryScopeError("tenant-as-user identity is refused for Radix memory")
    return tenant, user



def is_tenant_wide_kind(kind: str) -> bool:
    return str(kind) in TENANT_WIDE_KINDS


def _call_accepts(fn: Any, name: str) -> bool:
    try:
        import inspect
        return name in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


async def remember_for_actor(
    memory: Any,
    *,
    tenant_id: str,
    user_id: str,
    text: str,
    kind: str,
    source: str,
    meta: dict | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Pass verified Actor.user_id only. No product-side user filtering.

    Requires the fixed shared MemoryClient contract. Never fall back to
    tenant-only reads/writes when that dependency is missing.
    """
    tenant, user = require_authenticated_scope(tenant_id=tenant_id, user_id=user_id)
    wide = is_tenant_wide_kind(kind)
    if not wide and not user:
        raise MemoryScopeError("missing user_id refused for personal Radix memory kind")
    payload_meta = dict(meta or {})
    if wide:
        payload_meta.pop("user_id", None)
    else:
        payload_meta["user_id"] = user
    call_kwargs = dict(kwargs)
    call_kwargs["meta"] = payload_meta
    if not wide:
        call_kwargs["user_id"] = user
    if _call_accepts(memory.remember, "tenant_wide"):
        call_kwargs["tenant_wide"] = wide
    return await memory.remember(tenant, text, kind, source, **call_kwargs)


async def recall_for_actor(
    memory: Any,
    *,
    tenant_id: str,
    user_id: str,
    query: str,
    kind: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Pass verified Actor.user_id into shared recall. No product-side filter.

    An older tenant-only client is refused before any storage request.
    """
    tenant, user = require_authenticated_scope(tenant_id=tenant_id, user_id=user_id)
    kwargs: dict[str, Any] = {}
    if kind is not None:
        kwargs["kind"] = kind
    if limit is not None:
        kwargs["limit"] = limit
    kwargs["user_id"] = user
    return await memory.recall(tenant, query, **kwargs)

def _control_allows_recall(control: str) -> bool:
    return control in {"view", "edit", "forget"}


def _control_allows_remember(control: str) -> bool:
    return control in {"edit", "forget"}


def _control_allows_forget(control: str) -> bool:
    return control == "forget"


def task_input_hash(task: dict[str, Any] | None) -> str:
    payload = task if isinstance(task, dict) else {}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def is_cache_eligible(task_key: str, task: dict[str, Any] | None = None) -> bool:
    task = task or {}
    task_type = str(task.get("task_type") or task_key or "")
    return task_type in CACHE_ELIGIBLE_TASK_TYPES


def assert_remember_fields_nonempty(fields: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if value == "" or value == [] or value == {}:
            raise ValueError(f"Radix memory refuses empty remembered field: {key}")
        if isinstance(value, str) and not value.strip():
            raise ValueError(f"Radix memory refuses empty remembered field: {key}")
        if isinstance(value, (list, dict)) and len(value) == 0:
            raise ValueError(f"Radix memory refuses empty remembered field: {key}")
        cleaned[key] = value
    if not cleaned:
        raise ValueError("Radix memory refuses empty remember payload")
    return cleaned


def build_memory_text(
    *,
    sites_scanned: list[str] | None = None,
    findings: list[str] | None = None,
    fixes: list[str] | None = None,
    accepted_risks: list[str] | None = None,
    false_positives: list[str] | None = None,
    correction: str | None = None,
    receipt: str | None = None,
    summary: str | None = None,
    outcome: str | None = None,
) -> str:
    fields = assert_remember_fields_nonempty({
        "summary": summary,
        "outcome": outcome,
        "sites_scanned": sites_scanned,
        "findings": findings,
        "fixes": fixes,
        "accepted_risks": accepted_risks,
        "false_positives": false_positives,
        "correction": correction,
        "receipt": receipt,
    })
    parts: list[str] = []
    if "summary" in fields:
        parts.append(fields["summary"])
    if "outcome" in fields:
        parts.append("outcome=" + fields["outcome"])
    if "sites_scanned" in fields:
        parts.append("sites_scanned=" + ",".join(fields["sites_scanned"]))
    if "findings" in fields:
        parts.append("findings=" + ",".join(fields["findings"]))
    if "fixes" in fields:
        parts.append("fixes=" + ",".join(fields["fixes"]))
    if "accepted_risks" in fields:
        parts.append("accepted_risks=" + ",".join(fields["accepted_risks"]))
    if "false_positives" in fields:
        parts.append("false_positives=" + ",".join(fields["false_positives"]))
    if "correction" in fields:
        parts.append("correction=" + fields["correction"])
    if "receipt" in fields:
        parts.append("receipt=" + fields["receipt"])
    text = "; ".join(parts)
    if _text_has_secret(text):
        raise ValueError("Radix memory refuses secret-bearing text")
    return text


def select_tenant_user_memories(
    rows: list[dict[str, Any]], *, tenant_id: str, user_id: str,
) -> list[dict[str, Any]]:
    tenant, user = str(tenant_id), str(user_id)
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
        correction = (row.get("meta") or {}).get("correction")
        if isinstance(correction, str) and correction.strip():
            found.append(correction.strip())
            continue
        text = str(row.get("claim") or row.get("text") or "")
        marker = "correction="
        if marker in text:
            found.append(text.split(marker, 1)[1].split(";")[0].strip())
            continue
        if row.get("kind") == "radix.correction" and text.strip():
            found.append(text.strip())
    return found


def memory_control_from_memories(rows: list[dict[str, Any]]) -> str | None:
    for row in reversed(rows):
        if row.get("kind") != CONTROL_KIND:
            continue
        meta = row.get("meta") or {}
        if isinstance(meta, dict) and meta.get("control") in MEMORY_CONTROLS:
            return str(meta["control"])
        text = str(row.get("claim") or row.get("text") or "")
        marker = "memory_control="
        if marker in text:
            value = text.split(marker, 1)[1].split(";")[0].strip().lower()
            if value in MEMORY_CONTROLS:
                return value
    return None


def approved_result_from_memories(
    rows: list[dict[str, Any]], *, task_key: str, input_hash: str,
) -> dict[str, Any] | None:
    key, digest = str(task_key), str(input_hash)
    for row in reversed(rows):
        meta = row.get("meta") or {}
        if not isinstance(meta, dict):
            continue
        if not meta.get("approved"):
            continue
        if str(meta.get("task_key") or "") != key:
            continue
        if str(meta.get("input_hash") or "") != digest:
            continue
        if meta.get("invalidated"):
            continue
        if "result" not in meta:
            continue
        out = dict(meta)
        out["memory_id"] = row.get("id")
        return out
    return None


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
    return result


async def invalidate_task(memory, *, tenant_id: str, user_id: str, task_key: str, input_hash=None, forget=False):
    """Invalidate SQL-backed answers through the signed client, before mutation."""
    rows = await memory.records(tenant_id, user_id=user_id)
    for row in rows:
        meta = dict(row.get("meta") or {})
        if meta.get("task_key") != task_key or row.get("kind") == CONTROL_KIND:
            continue
        if input_hash is not None and meta.get("input_hash") != input_hash:
            continue
        if forget:
            await memory.forget(str(row["id"]), tenant_id, user_id=user_id)
        elif meta.get("approved"):
            meta.update(approved=False, invalidated=True)
            await remember_for_actor(memory, tenant_id=tenant_id, user_id=user_id,
                text=row.get("claim") or row.get("text") or "Invalidated Radix answer",
                kind=row["kind"], source=row.get("source") or "radix:invalidate",
                meta=meta, record_id=str(row["id"]), replace=True)


async def resolve_memory_control(
    memory: Any, *, tenant_id: str, user_id: str, override: str | None = None,
) -> str:
    if override is not None:
        return normalize_memory_control(override)
    if memory is None or not callable(getattr(memory, "recall", None)):
        return "edit"
    scoped = await memory.records(str(tenant_id), user_id=str(user_id))

    found = memory_control_from_memories(scoped)
    return normalize_memory_control(found or "edit")


async def require_owned_record(
    memory: Any, *, memory_id: str, tenant_id: str, user_id: str,
) -> dict[str, Any]:
    """Refuse unless the target record's tenant AND user match the signed-in caller."""
    tenant, user = require_authenticated_scope(tenant_id=tenant_id, user_id=user_id)
    if not str(memory_id).strip():
        raise MemoryScopeError("memory_id required for scoped memory control")
    rows = await memory.records(tenant, user_id=user)
    match = None
    for row in rows or []:
        if str(row.get("id")) != str(memory_id):
            continue
        if str(row.get("tenant_id", "")) != tenant:
            continue
        meta = row.get("meta") or {}
        if not isinstance(meta, dict) or str(meta.get("user_id", "")) != user:
            continue
        match = row
        break
    if match is None:
        raise MemoryScopeError(
            "refused: target memory tenant+user do not match signed-in caller"
        )
    return match


async def set_memory_control(
    memory: Any, *, tenant_id: str, user_id: str, control: str,
    memory_id: str | None = None,
) -> dict[str, Any]:
    """Per-tenant+user switch-off / control via MemoryClient.remember."""
    tenant, user = require_authenticated_scope(tenant_id=tenant_id, user_id=user_id)
    if memory_id is not None:
        await require_owned_record(memory, memory_id=memory_id, tenant_id=tenant, user_id=user)
    normalized = normalize_memory_control(control)
    rows = await memory.records(tenant, user_id=user)
    existing = next((row for row in rows if row.get("kind") == CONTROL_KIND), None)
    return await remember_for_actor(
        memory, tenant_id=tenant, user_id=user,
        text=f"Radix memory_control={normalized}", kind=CONTROL_KIND, source=CONTROL_SOURCE,
        meta={"user_id": user, "control": normalized, "task_key": "memory_control"},
        **({"record_id": str(existing["id"]), "replace": True} if existing else {}),
    )



async def view_memories(
    memory: Any, *, tenant_id: str, user_id: str, task_key: str = "memory_control",
    memory_id: str | None = None,
) -> dict[str, Any]:
    tenant, user = require_authenticated_scope(tenant_id=tenant_id, user_id=user_id)
    control = await resolve_memory_control(memory, tenant_id=tenant, user_id=user)
    if control == "off":
        return {"memories": [], "memory_control": control}
    if memory_id is not None:
        owned = await require_owned_record(
            memory, memory_id=memory_id, tenant_id=tenant, user_id=user
        )
        return {"memories": [owned], "memory_control": control}
    scoped = await recall_for_actor(
        memory, tenant_id=tenant, user_id=user, query=task_key, kind=None, limit=50,
    )
    return {"memories": scoped, "memory_control": control}


async def apply_memory_edit(
    memory: Any, *, memory_id: str, tenant_id: str, user_id: str, text: str,
    memory_control: str | None = None,
) -> dict[str, Any]:
    tenant, user = require_authenticated_scope(tenant_id=tenant_id, user_id=user_id)
    control = await resolve_memory_control(
        memory, tenant_id=tenant, user_id=user, override=memory_control
    )
    if not _control_allows_remember(control):
        raise MemoryControlError(f"memory control {control!r} refuses content edit")
    if not str(text).strip():
        raise ValueError("memory edit requires non-empty text")
    if _text_has_secret(text):
        raise ValueError("Radix memory refuses secret-bearing text")
    row = await require_owned_record(
        memory, memory_id=memory_id, tenant_id=tenant, user_id=user
    )
    meta = dict(row.get("meta") or {})
    key = meta.get("task_key")
    if key:
        await invalidate_task(memory, tenant_id=tenant, user_id=user, task_key=key, input_hash=meta.get("input_hash"))
    # A correction is user-supplied evidence, never an approved old answer.
    meta.pop("result", None)
    meta.update(user_id=user, edited=True, approved=False, invalidated=False, correction=text.strip())
    return await remember_for_actor(
        memory, tenant_id=tenant, user_id=user, text=text.strip(), kind=row["kind"],
        source=str(row.get("source") or f"radix:edit:{memory_id}"), meta=meta,
        record_id=str(memory_id), replace=True,
    )



async def apply_memory_forget(
    memory: Any, *, memory_id: str, tenant_id: str, user_id: str,
    memory_control: str = "forget",
) -> None:
    tenant, user = require_authenticated_scope(tenant_id=tenant_id, user_id=user_id)
    control = await resolve_memory_control(
        memory, tenant_id=tenant, user_id=user, override=memory_control
    )
    if not _control_allows_forget(control):
        raise MemoryControlError(f"memory control {control!r} refuses forget")
    row = await require_owned_record(memory, memory_id=memory_id, tenant_id=tenant, user_id=user)
    key = (row.get("meta") or {}).get("task_key")
    if key and row.get("kind") != CONTROL_KIND:
        await invalidate_task(memory, tenant_id=tenant, user_id=user, task_key=key,
                              input_hash=(row.get("meta") or {}).get("input_hash"), forget=True)
    else:
        await memory.forget(memory_id, tenant, user_id=user)


async def run_with_memory(
    memory: Any, *, tenant_id: str, user_id: str, task_key: str, task: dict[str, Any],
    paid_call: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    memory_control: str | None = None,
    code_free: Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Code first, verified personal memory, then the existing Tank route.

    The worker checkpoints execution before remember. Authentication errors
    propagate; storage failures are recorded and never re-enter paid execution.
    """
    tenant, user = require_authenticated_scope(tenant_id=tenant_id, user_id=user_id)
    unavailable = False
    try:
        control = await resolve_memory_control(memory, tenant_id=tenant, user_id=user, override=memory_control)
    except Exception as exc:
        if not is_memory_outage(exc):
            raise
        unavailable, control = True, "off"
    digest = task_input_hash(task)
    receipt = dict(tenant_id=tenant, user_id=user, task_key=task_key, input_hash=digest,
        cache_eligible=is_cache_eligible(task_key, task), memory_control=control,
        steps=[], cost_usd=0.0, tokens_in=0, tokens_out=0, paid_calls=0,
        answered_from_memory=False, would_have_cost=None, result=None,
        memory_enabled=control != "off", status="completed")
    if unavailable:
        receipt["memory_unavailable"] = True
        receipt["steps"].append({"action": "memory_unavailable", "phase": "list"})
    free = None
    if code_free is not None:
        free = await code_free(task)
        receipt["steps"].append({"action": "code_skill", "hit": free is not None})
    scoped = []
    if free is None and control != "off":
        try:
            recalled = await recall_for_actor(memory, tenant_id=tenant, user_id=user, query=task_key, limit=50)
            # The durable list prevents an indexing delay from reviving stale
            # cache metadata or hiding a committed correction/control change.
            rows = await memory.records(tenant, user_id=user)
            scoped = [row for row in rows if (row.get("meta") or {}).get("task_key") == task_key
                      and (row.get("meta") or {}).get("input_hash", digest) == digest]
            receipt["steps"].append({"action": "recall", "count": len(recalled), "memory_ids": [r["id"] for r in recalled]})
        except Exception as exc:
            if not is_memory_outage(exc):
                raise
            unavailable = True
            receipt["memory_unavailable"] = True
            receipt["steps"].append({"action": "memory_unavailable", "phase": "recall"})
        if not unavailable:
            corrections = corrections_from_memories(scoped)
            if corrections:
                await invalidate_task(memory, tenant_id=tenant, user_id=user, task_key=task_key, input_hash=digest)
                receipt.update(result=apply_corrections(task, corrections), answered_from_memory=True)
                receipt["steps"].append({"action": "apply_correction", "corrections": corrections})
                return receipt
            approved = approved_result_from_memories(scoped, task_key=task_key, input_hash=digest) if receipt["cache_eligible"] else None
            if approved is not None:
                receipt.update(result=deepcopy(approved["result"]), answered_from_memory=True,
                    would_have_cost=approved.get("would_have_cost", approved.get("cost_usd")))
                receipt["steps"].append({"action": "answer_from_memory", "memory_id": approved["memory_id"]})
                return receipt
    if free is not None:
        executed = free
        receipt["steps"].append({"action": "code_free_done"})
    else:
        if control == "off":
            receipt["steps"].append({"action": "memory_off"})
        executed = await paid_call(task)
        receipt["paid_calls"] = executed.get("paid_calls", 1)
        receipt["steps"].append({"action": "brain_route", "status": executed.get("status", "done")})
    for field in ("cost_usd", "tokens_in", "tokens_out"):
        receipt[field] = executed.get(field, 0 if free is not None else None)
    receipt["result"] = executed.get("result", executed)
    receipt["status"] = executed.get("status", "completed")
    if executed.get("tank_receipt"):
        receipt["tank_receipt"] = executed["tank_receipt"]
    if executed.get("ledger_id"):
        receipt["ledger_id"] = executed["ledger_id"]
    receipt["would_have_cost"] = executed.get("would_have_cost", receipt["cost_usd"])
    if (not persist or not _control_allows_remember(control) or unavailable or receipt["status"] != "completed"
            or (free is not None and not receipt["cache_eligible"])):
        return receipt
    result = receipt["result"]
    if not isinstance(result, dict):
        raise ValueError("Radix result must be an object")
    fields = {}
    for field in ("sites_scanned", "findings", "fixes", "accepted_risks", "false_positives"):
        values = result.get(field)
        if values:
            fields[field] = [v if isinstance(v, str) else json.dumps(v, sort_keys=True) for v in values]
    correction = result.get("correction")
    text = build_memory_text(summary=f"Radix task {task_key}", outcome=receipt["status"],
        correction=correction, receipt=f"cost={receipt['cost_usd']};tokens_in={receipt['tokens_in']};tokens_out={receipt['tokens_out']}", **fields)
    # Validate both text and cache content before any personal write.
    if _text_has_secret(json.dumps(result, sort_keys=True)):
        raise ValueError("Radix memory refuses secret-bearing content")
    meta = dict(user_id=user, task_key=task_key, input_hash=digest)
    if not correction:
        meta.update(approved=True, result=deepcopy(result), would_have_cost=receipt["would_have_cost"],
            cost_usd=receipt["cost_usd"], tokens_in=receipt["tokens_in"], tokens_out=receipt["tokens_out"], invalidated=False)
    try:
        if correction:
            await invalidate_task(memory, tenant_id=tenant, user_id=user, task_key=task_key, input_hash=digest)
        saved = await remember_for_actor(memory, tenant_id=tenant, user_id=user, text=text,
            kind="radix.correction" if correction else "radix.receipt", source=f"radix:task:{task_key}", meta=meta)
    except Exception as exc:
        if not is_memory_outage(exc):
            raise
        receipt["memory_unavailable"] = True
        receipt["steps"].append({"action": "memory_unavailable", "phase": "remember"})
        return receipt
    receipt["steps"].append({"action": "remember", "memory_id": saved["id"], "source": f"radix:task:{task_key}"})
    return receipt


async def analyze_via_memory(memory, *, actor, run_id, site, tank,
    task_key="radix.site_risk", memory_control=None, persist=True, code_free=None):
    from radix_brain import brain_then_analyze
    async def paid(task):
        return await brain_then_analyze(actor, run_id=run_id, tank=tank, evidence=task)
    return await run_with_memory(memory, tenant_id=actor.tenant_id, user_id=actor.user_id,
        task_key=task_key, task={"site": site}, paid_call=paid,
        memory_control=memory_control, persist=persist, code_free=code_free)
