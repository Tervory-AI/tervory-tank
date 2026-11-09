"""Gates 7+8 memory bracket for Market Lab: free steps first, then brain/Tank.

Uses the product's existing memory client (ctx.memory / MemoryClient) only.
Tenant and user scope never cross. Secrets are refused. Corrections and prior
identical receipts recalled from memory are applied before any paid brain or
Tank route.

What Market Lab remembers: questions asked, sources trusted and rejected, past
reports, corrections to findings, watchlists, outcome and receipt — every field
carries a real value (never hardcoded empty). Tenant-wide kinds are declared in
tenant_wide_kinds(); everything else is personal and carries meta.user_id via
the shipped chassis client; fixed Hermes enforces central ownership.

View / edit / forget / switch-off are per tenant+user via MemoryClient. The
product passes only the verified actor's user_id (never a request-body user)
and does no recall-time user filtering of its own. Actor mismatch is refused
before any read or mutation.
"""
from __future__ import annotations

import hashlib
import json
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

MEMORY_CONTROLS = frozenset({"off", "view", "edit", "forget"})
CONTROL_KIND = "market_lab.memory_control"
CONTROL_SOURCE = "market_lab:memory_control"

FIXED_FAKE_PER_CALL = {"cost_usd": 0.05, "tokens_in": 10, "tokens_out": 3}

CACHE_ELIGIBLE_TASK_TYPES = frozenset(
    {
        "market.research",
        "research-cost-twice",
        "research-ffl-capacity",
        "research-source-retry",
    }
)


class MemoryScopeError(ValueError):
    """Tenant/user scope refused."""


class MemoryControlError(ValueError):
    """Memory control refuses the requested action."""


class MemoryIdentityError(ValueError):
    """Verified signed-in actor proof missing or invalid."""


def _text_has_secret(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in FORBIDDEN_SECRET_MARKERS)


def memory_kinds() -> frozenset[str]:
    return frozenset(
        {
            "market_lab.question",
            "market_lab.trusted_source",
            "market_lab.rejected_source",
            "market_lab.report",
            "market_lab.correction",
            "market_lab.watchlist",
            "market_lab.receipt",
            "market_lab.task",
            CONTROL_KIND,
            # Tenant-wide kinds (no meta.user_id). Declared here for the chassis/Hermes
            # central declaration; Market Lab task memory is personal by default.
            "warning_pattern",
        }
    )


def tenant_wide_kinds() -> frozenset[str]:
    """Record types that belong to the whole client (no user_id).

    Personal kinds require the verified actor user_id. Fixed chassis/Hermes
    enforce this centrally; the product only passes the
    actor's user_id and never filters recall rows itself.
    """
    return frozenset({"warning_pattern"})


def normalize_memory_control(value: Any) -> str:
    control = str(value or "edit").strip().lower()
    if control not in MEMORY_CONTROLS:
        raise ValueError(f"unsupported memory control: {control}")
    return control


def require_authenticated_scope(*, tenant_id: Any, user_id: Any) -> tuple[str, str]:
    from uuid import UUID

    if tenant_id in (None, ""):
        raise MemoryScopeError("authenticated tenant_id required for Market Lab memory")
    tenant = str(tenant_id).strip()
    if not tenant:
        raise MemoryScopeError("authenticated tenant_id required for Market Lab memory")
    try:
        tenant = str(UUID(tenant))
    except (ValueError, TypeError, AttributeError) as exc:
        raise MemoryScopeError("authenticated tenant_id required for Market Lab memory") from exc
    if user_id in (None, ""):
        raise MemoryScopeError("authenticated user_id required for Market Lab memory")
    user = str(user_id).strip()
    if not user:
        raise MemoryScopeError("authenticated user_id required for Market Lab memory")
    return tenant, user


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
    return task_type in CACHE_ELIGIBLE_TASK_TYPES or task_type.startswith("research-")


def assert_remember_fields_nonempty(fields: dict[str, Any]) -> dict[str, Any]:
    """Every field written by remember must carry a real value — never '' / [] / {} / None."""
    cleaned: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if value == "" or value == [] or value == {}:
            raise ValueError(f"Market Lab memory refuses empty remembered field: {key}")
        if isinstance(value, str) and not value.strip():
            raise ValueError(f"Market Lab memory refuses empty remembered field: {key}")
        if isinstance(value, (list, dict)) and len(value) == 0:
            raise ValueError(f"Market Lab memory refuses empty remembered field: {key}")
        cleaned[key] = value
    if not cleaned:
        raise ValueError("Market Lab memory refuses empty remember payload")
    return cleaned


def build_memory_text(
    *,
    questions: list[str] | None = None,
    trusted_sources: list[str] | None = None,
    rejected_sources: list[str] | None = None,
    reports: list[str] | None = None,
    corrections: list[str] | None = None,
    watchlists: list[str] | None = None,
    correction: str | None = None,
    receipt: str | None = None,
    summary: str | None = None,
    outcome: str | None = None,
) -> str:
    fields = assert_remember_fields_nonempty(
        {
            "summary": summary,
            "outcome": outcome,
            "questions": questions,
            "trusted_sources": trusted_sources,
            "rejected_sources": rejected_sources,
            "reports": reports,
            "corrections": corrections,
            "watchlists": watchlists,
            "correction": correction,
            "receipt": receipt,
        }
    )
    parts: list[str] = []
    if "summary" in fields:
        parts.append(fields["summary"])
    if "outcome" in fields:
        parts.append("outcome=" + fields["outcome"])
    if "questions" in fields:
        parts.append("questions=" + ",".join(fields["questions"]))
    if "trusted_sources" in fields:
        parts.append("trusted_sources=" + ",".join(fields["trusted_sources"]))
    if "rejected_sources" in fields:
        parts.append("rejected_sources=" + ",".join(fields["rejected_sources"]))
    if "reports" in fields:
        parts.append("reports=" + ",".join(fields["reports"]))
    if "corrections" in fields:
        parts.append("corrections=" + ",".join(fields["corrections"]))
    if "watchlists" in fields:
        parts.append("watchlists=" + ",".join(fields["watchlists"]))
    if "correction" in fields:
        parts.append("correction=" + fields["correction"])
    if "receipt" in fields:
        parts.append("receipt=" + fields["receipt"])
    text = "; ".join(parts)
    if _text_has_secret(text):
        raise ValueError("Market Lab memory refuses secret-bearing text")
    return text


def select_tenant_user_memories(
    rows: list[dict[str, Any]],
    *,
    tenant_id: str,
    user_id: str,
) -> list[dict[str, Any]]:
    """Test/inspection helper only — NOT used on the product recall path (t51)."""
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


def _remember_kwargs(*, user_id: str, kind: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pass verified actor user_id into MemoryClient; never a request-body user."""
    payload = dict(meta or {})
    kwargs: dict[str, Any] = {
        "meta": payload,
        "user_id": str(user_id),
    }
    return kwargs


def corrections_from_memories(rows: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    for row in rows:
        text = str(row.get("text", ""))
        marker = "correction="
        if marker in text:
            found.append(text.split(marker, 1)[1].split(";")[0].strip())
            continue
        if row.get("kind") == "market_lab.correction" and text.strip():
            found.append(text.strip())
    return found


def memory_control_from_memories(rows: list[dict[str, Any]]) -> str | None:
    for row in reversed(rows):
        if row.get("kind") != CONTROL_KIND:
            continue
        meta = row.get("meta") or {}
        if isinstance(meta, dict) and meta.get("control") in MEMORY_CONTROLS:
            return str(meta["control"])
        text = str(row.get("text", ""))
        marker = "memory_control="
        if marker in text:
            value = text.split(marker, 1)[1].split(";")[0].strip().lower()
            if value in MEMORY_CONTROLS:
                return value
    return None


def approved_result_from_memories(
    rows: list[dict[str, Any]],
    *,
    task_key: str,
    input_hash: str,
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
        return {**meta,"memory_id":str(row["id"])}
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
    result["content"] = "\n".join(corrections)
    return result


async def resolve_memory_control(
    memory: Any,
    *,
    tenant_id: str,
    user_id: str,
    override: str | None = None,
) -> str:
    if override is not None:
        return normalize_memory_control(override)
    if memory is None or not callable(getattr(memory, "recall", None)):
        return "edit"
    if callable(getattr(memory, 'records', None)):
        recalled = await memory.records(str(tenant_id), user_id=str(user_id))
        recalled = list(reversed(recalled))  # SQL records are newest first.
    else:
        recalled = await memory.recall(str(tenant_id), 'memory_control', kind=CONTROL_KIND, limit=16, user_id=str(user_id))
    found = memory_control_from_memories(recalled)
    return normalize_memory_control(found or "edit")


async def require_owned_record(
    memory: Any,
    *,
    memory_id: str,
    tenant_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Refuse unless the target record's tenant AND user match the signed-in caller."""
    tenant, user = require_authenticated_scope(tenant_id=tenant_id, user_id=user_id)
    if not str(memory_id).strip():
        raise MemoryScopeError("memory_id required for scoped memory control")
    if hasattr(memory, "records"):
        try:
            rows = await memory.records(
                tenant, user_id=user
            )
        except TypeError:
            rows = await memory.records(tenant)
    else:
        rows = getattr(memory, "rows", [])
    match = None
    for row in rows or []:
        if str(row.get("id")) != str(memory_id):
            continue
        if str(row.get("tenant_id", "")) != tenant:
            continue
        # Actor ownership: personal row must carry this actor's user_id.
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
    memory: Any,
    *,
    tenant_id: str,
    user_id: str,
    control: str,
    memory_id: str | None = None,
) -> dict[str, Any]:
    """Per-tenant+user switch-off / control via MemoryClient.remember."""
    tenant, user = require_authenticated_scope(tenant_id=tenant_id, user_id=user_id)
    if memory_id is not None:
        await require_owned_record(memory, memory_id=memory_id, tenant_id=tenant, user_id=user)
    normalized = normalize_memory_control(control)
    text = build_memory_text(
        summary=f"Market Lab memory_control for user {user}",
        outcome=f"control:{normalized}",
        receipt=f"control={normalized}",
        questions=["memory-control"],
        trusted_sources=["memory-client"],
        rejected_sources=["foreign-actor"],
        reports=[f"control-{normalized}"],
        corrections=[f"set-control-{normalized}"],
        watchlists=["memory-controls"],
    )
    return await memory.remember(
        tenant,
        text,
        CONTROL_KIND,
        CONTROL_SOURCE,
        **_remember_kwargs(
            user_id=user,
            kind=CONTROL_KIND,
            meta={"control": normalized, "task_key": "memory_control"},
        ),
    )


async def view_memories(
    memory: Any,
    *,
    tenant_id: str,
    user_id: str,
    task_key: str = "memory_control",
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
    recalled = await memory.recall(
        tenant,
        task_key,
        kind=None,
        limit=50,
        user_id=user,
    )
    return {"memories": recalled, "memory_control": control}


async def apply_memory_edit(
    memory: Any,
    *,
    memory_id: str,
    tenant_id: str,
    user_id: str,
    text: str,
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
        raise ValueError("Market Lab memory refuses secret-bearing text")
    row = await require_owned_record(
        memory, memory_id=memory_id, tenant_id=tenant, user_id=user
    )
    kind = str(row.get("kind") or "market_lab.task")
    return await memory.remember(
        tenant,
        text.strip(),
        kind,
        str(row.get("source") or f"market_lab:edit:{memory_id}"),
        record_id=str(memory_id),
        replace=True,
        **_remember_kwargs(
            user_id=user,
            kind=kind,
            meta={**(row.get("meta") or {}), "edited": True, "invalidated": True},
        ),
    )


async def apply_memory_forget(
    memory: Any,
    *,
    memory_id: str,
    tenant_id: str,
    user_id: str,
    memory_control: str = "forget",
) -> None:
    tenant, user = require_authenticated_scope(tenant_id=tenant_id, user_id=user_id)
    control = await resolve_memory_control(
        memory, tenant_id=tenant, user_id=user, override=memory_control
    )
    if not _control_allows_forget(control):
        raise MemoryControlError(f"memory control {control!r} refuses forget")
    await require_owned_record(memory, memory_id=memory_id, tenant_id=tenant, user_id=user)
    await memory.forget(memory_id, tenant, user_id=user)


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
        record_id: str | None = None,
        replace: bool = False,
        user_id: str | None = None,
        tenant_wide_kinds: list[str] | tuple[str, ...] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        if kind not in memory_kinds():
            raise ValueError("unsupported Market Lab memory kind")
        if _text_has_secret(text):
            raise ValueError("Market Lab memory refuses secret-bearing text")
        if not str(text).strip():
            raise ValueError("Market Lab memory refuses empty remember text")
        wide_arg = tenant_wide_kinds
        wide = {str(item) for item in (wide_arg if wide_arg is not None else globals()["tenant_wide_kinds"]())}
        payload = dict(meta or {})
        if kind in wide and not user_id and not payload.get("user_id"):
            payload.pop("user_id", None)
        else:
            effective = user_id if user_id not in (None, "") else payload.get("user_id")
            if effective in (None, ""):
                raise ValueError("user_id required for personal memory kind")
            payload["user_id"] = str(effective)
        tenant = str(tenant_id)
        if record_id is not None:
            for row in self.rows:
                if row["id"] == str(record_id) and row["tenant_id"] == tenant:
                    row["text"] = text
                    row["kind"] = kind
                    row["source"] = source
                    row["meta"] = payload
                    self.remembers += 1
                    return {"id": row["id"], "seen": self.remembers, "updated": True}
            raise ValueError("remember update refused: memory not found for tenant")
        row = {
            "id": f"mem-{len(self.rows) + 1}",
            "tenant_id": tenant,
            "text": text,
            "kind": kind,
            "source": source,
            "meta": payload,
        }
        self.rows.append(row)
        self.remembers += 1
        return {"id": row["id"], "seen": self.remembers}

    async def recall(
        self,
        tenant_id: str,
        query: str,
        *,
        kind: str | None = None,
        limit: int | None = None,
        user_id: str | None = None,
        tenant_wide_kinds: list[str] | tuple[str, ...] | None = None,
        **_: Any,
    ) -> list[dict[str, Any]]:
        self.recalls += 1
        tenant = str(tenant_id)
        wide_arg = tenant_wide_kinds
        wide = {str(item) for item in (wide_arg if wide_arg is not None else globals()["tenant_wide_kinds"]())}
        matches: list[dict[str, Any]] = []
        for row in self.rows:
            if row["tenant_id"] != tenant:
                continue
            if kind is not None and row["kind"] != kind:
                continue
            # Central user scope (mirrors unapplied Hermes proposal).
            if user_id not in (None, ""):
                meta = row.get("meta") or {}
                owner = str(meta.get("user_id") or "") if isinstance(meta, dict) else ""
                if owner == str(user_id):
                    pass
                elif not owner and row["kind"] in wide:
                    pass
                else:
                    continue
            if not (
                not query
                or query.lower() in row["text"].lower()
                or query == (row.get("meta") or {}).get("task_key")
                or query == (row.get("meta") or {}).get("control")
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

    async def records(
        self,
        tenant_id: str,
        *,
        tier: str = "client",
        user_id: str | None = None,
        tenant_wide_kinds: list[str] | tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        del tier
        wide_arg = tenant_wide_kinds
        wide = {str(item) for item in (wide_arg if wide_arg is not None else globals()["tenant_wide_kinds"]())}
        kept = []
        for row in self.rows:
            if row["tenant_id"] != str(tenant_id):
                continue
            if user_id not in (None, ""):
                meta = row.get("meta") or {}
                owner = str(meta.get("user_id") or "") if isinstance(meta, dict) else ""
                if owner == str(user_id):
                    pass
                elif not owner and row["kind"] in wide:
                    pass
                else:
                    continue
            kept.append(row)
        return deepcopy(list(reversed(kept)))


async def run_with_memory(
    memory: Any,
    *,
    tenant_id: str,
    user_id: str,
    task_key: str,
    task: dict[str, Any],
    paid_call: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    memory_control: str | None = None,
    code_free: Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Product request → free steps (code, recall, cache) → brain/Tank → remember.

    Exact uncorrected repeats (same tenant, user, task_key, input hash) return
    from memory with paid_calls=0, cost_usd=0.0, tokens 0/0 and would_have_cost
    before any brain or Tank paid route.
    """
    tenant, user = require_authenticated_scope(tenant_id=tenant_id, user_id=user_id)
    from core.personal import memory_enabled
    control_failure = False
    try:
        control = await resolve_memory_control(memory, tenant_id=tenant, user_id=user, override=memory_control) if memory_enabled() else 'off'
    except Exception as exc:
        if isinstance(exc, (MemoryScopeError, ValueError, TypeError)) or any(code in str(exc) for code in ('401', '403')):
            raise MemoryScopeError('Memory identity refused') from None
        control, control_failure = 'off', True
    input_hash = task_input_hash(task)
    cache_eligible = is_cache_eligible(task_key, task)
    can_recall = memory is not None and callable(getattr(memory, "recall", None))
    can_remember = memory is not None and callable(getattr(memory, "remember", None))
    receipt: dict[str, Any] = {
        "tenant_id": tenant,
        "user_id": user,
        "task_key": task_key,
        "input_hash": input_hash,
        "cache_eligible": cache_eligible,
        "memory_control": control,
        "steps": [],
        "cost_usd": 0.0,
        "tokens_in": 0,
        "tokens_out": 0,
        "paid_calls": 0,
        "answered_from_memory": False,
        "would_have_cost": None,
        "result": None,
        "memory_enabled": control != "off",
    }

    if control_failure:
        receipt['memory_unavailable'] = True
        receipt['steps'].append({'action': 'memory_unavailable', 'phase': 'list'})

    # Free step 1: deterministic code skill before any paid route (Base pattern).
    if code_free is not None:
        free = await code_free(task)
        receipt["steps"].append({"action": "code_skill", "hit": bool(free)})
        if free is not None:
            receipt["result"] = free.get("result", free)
            receipt["steps"].append({"action": "code_free_done"})
            return receipt

    # Per-tenant+user switch-off: never serve from memory; always pay.
    if control == "off":
        receipt["steps"].append({"action": "memory_off"})
        paid = await paid_call(task)
        receipt["paid_calls"] = paid.get("paid_calls", 1)
        receipt["cost_usd"] = None if paid.get("cost_usd",0) is None else float(paid.get("cost_usd",0))
        receipt["tokens_in"] = int(paid.get("tokens_in") or 0)
        receipt["tokens_out"] = int(paid.get("tokens_out") or 0)
        receipt["result"] = paid.get("result", paid)
        receipt["steps"].append({"action": "brain_route", "status": "done"})
        return receipt

    memory_unavailable = False
    if can_recall and _control_allows_recall(control):
        try:
            recalled = await memory.recall(
                tenant,
                task_key,
                kind=None,
                limit=32,
                user_id=user,
                )
        except Exception as exc:
            if isinstance(exc, (MemoryScopeError, ValueError, TypeError)) or any(code in str(exc) for code in ('401','403')):
                raise MemoryScopeError('Memory identity refused') from None
            # Memory service outage: answer without memory; never serve a stored repeat.
            memory_unavailable = True
            recalled = []
            receipt["memory_unavailable"] = True
            receipt["steps"].append({"action": "memory_unavailable"})
        if not memory_unavailable:
            receipt["steps"].append(
                {
                    "action": "recall",
                    "count": len(recalled),
                    "memory_ids": [r["id"] for r in recalled],
                }
            )
            corrections = corrections_from_memories(recalled)
            if corrections:
                result = apply_corrections(task, corrections)
                receipt["answered_from_memory"] = True
                receipt["result"] = result
                receipt["steps"].append(
                    {"action": "apply_correction", "corrections": corrections}
                )
                return receipt
            if cache_eligible:
                approved = approved_result_from_memories(
                    recalled, task_key=task_key, input_hash=input_hash
                )
                if approved is not None:
                    would_have = approved.get('would_have_cost', approved.get('cost_usd'))
                    receipt["answered_from_memory"] = True
                    receipt["result"] = deepcopy(approved.get("result"))
                    receipt["would_have_cost"] = would_have
                    receipt["paid_calls"] = 0
                    receipt["cost_usd"] = 0.0
                    receipt["tokens_in"] = 0
                    receipt["tokens_out"] = 0
                    receipt["steps"].append(
                        {
                            "action": "answer_from_memory",
                            "memory_id": approved.get("memory_id"),
                            "would_have_cost": would_have,
                        }
                    )
                    return receipt
    else:
        receipt["steps"].append(
            {
                "action": "recall",
                "count": 0,
                "memory_ids": [],
                "recall_available": can_recall,
            }
        )

    paid = await paid_call(task)
    receipt["paid_calls"] = paid.get("paid_calls", 1)
    receipt["cost_usd"] = None if paid.get("cost_usd",0) is None else float(paid.get("cost_usd",0))
    receipt["tokens_in"] = int(paid.get("tokens_in") or 0)
    receipt["tokens_out"] = int(paid.get("tokens_out") or 0)
    receipt["result"] = paid.get("result", paid)
    receipt["steps"].append({"action": "brain_route", "status": "done"})

    if not (persist and can_remember and _control_allows_remember(control)):
        return receipt
    if isinstance(receipt.get('result'),dict) and receipt['result'].get('status') in {'empty','unavailable','failed','error'}:
        return receipt

    result = receipt["result"] or {}
    questions = list(result.get("questions") or []) or [str(task.get("question") or task_key)]
    trusted = list(result.get("trusted_sources") or [])
    rejected = list(result.get("rejected_sources") or [])
    reports = list(result.get("reports") or [])
    watchlists = list(result.get("watchlists") or [])
    correction = result.get("correction")
    text_body = build_memory_text(
        summary=f"Market Lab task {task_key}",
        outcome=f"answered:{task_key}",
        questions=questions,
        trusted_sources=trusted or None,
        rejected_sources=rejected or None,
        reports=reports or None,
        corrections=list(result.get("corrections") or []) or None,
        watchlists=watchlists or None,
        correction=correction,
        receipt=(
            f"cost={receipt['cost_usd']};tokens_in={receipt['tokens_in']};"
            f"tokens_out={receipt['tokens_out']};input_hash={input_hash}"
        ),
    )
    kind = "market_lab.correction" if correction else "market_lab.receipt"
    meta: dict[str, Any] = {
        "task_key": task_key,
        "input_hash": input_hash,
    }
    if receipt["paid_calls"] == 1 and not correction:
        meta["approved"] = True
        meta["result"] = deepcopy(receipt["result"])
        meta["would_have_cost"] = receipt["cost_usd"]
        meta["cost_usd"] = receipt["cost_usd"]
        meta["tokens_in"] = int(receipt["tokens_in"])
        meta["tokens_out"] = int(receipt["tokens_out"])
    try:
        saved = await memory.remember(
            tenant,
            text_body,
            kind,
            f"market_lab:task:{task_key}",
            **_remember_kwargs(user_id=user, kind=kind, meta=meta),
        )
    except Exception:
        receipt["memory_unavailable"] = True
        receipt["steps"].append({"action": "memory_unavailable", "phase": "remember"})
        return receipt
    if meta.get("approved"):
        for row in getattr(memory, "rows", []):
            if row.get("id") == saved["id"]:
                row_meta = row.get("meta") or {}
                row_meta["memory_id"] = saved["id"]
                row["meta"] = row_meta
                break
    receipt["steps"].append(
        {"action": "remember", "memory_id": saved["id"], "source": f"market_lab:task:{task_key}"}
    )
    return receipt


async def research_via_memory(
    memory: Any,
    *,
    tenant_id: str,
    user_id: str,
    question: str,
    paid_run_id=None,
    task_key: str = "market.research",
    memory_control: str | None = None,
    persist: bool = True,
    code_free: Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]] | None = None,
    on_result=None,
    actor=None,
    tank_client=None,
) -> dict[str, Any]:
    """Production ask/research path: free steps → brain/Tank → remember."""
    from market_lab_brain import brain_then_research

    async def paid_call(task: dict[str, Any]) -> dict[str, Any]:
        paid = await brain_then_research(
            str(tenant_id),
            str(task.get("question") or question),
            paid_run_id=paid_run_id,
            task_id=task_key,
            actor=actor,
            tank_client=tank_client,
        )
        if on_result and paid.get('result',{}).get('facts'):
            paid['result'] = await on_result(paid['result'])
        return paid

    return await run_with_memory(
        memory,
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        task_key=task_key,
        task={"question": question, "tenant_id": str(tenant_id), "task_key": task_key},
        paid_call=paid_call,
        memory_control=memory_control,
        code_free=code_free,
        persist=persist,
    )
