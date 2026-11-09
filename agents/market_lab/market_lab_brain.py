"""Opt-in Market Lab work through Tank's signed, receipted task client."""
from __future__ import annotations

import os
from typing import Any
from uuid import uuid4


def brain_enabled() -> bool:
    return os.environ.get("MARKET_LAB_BRAIN_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


async def post_task(*, actor, run_id: str, task_key: str, payload: dict[str, Any], tank_client,
                    recall: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Tank alone discovers the optional private runtime and validates its receipt."""
    if not brain_enabled():
        raise RuntimeError("Market Lab brain is off")
    if actor is None or tank_client is None:
        raise ValueError("Verified actor and Tank client required")
    return await tank_client.delegate_task(actor, run_id, task_key, payload, recall or [])


async def brain_route(task: dict[str, Any], *, actor, tank_client, run_id: str) -> dict[str, Any]:
    data = await post_task(actor=actor, run_id=run_id, task_key=task["task_key"],
                           payload=task.get("payload") or {}, tank_client=tank_client)
    receipt = data["receipt"]
    return {"cost_usd": receipt["cost_usd"], "tokens_in": receipt["tokens_in"],
            "tokens_out": receipt["tokens_out"], "result": data["result"], "receipt": receipt}


async def brain_then_research(
    tenant_id: str,
    question: str,
    *,
    paid_run_id=None,
    task_id: str | None = None,
    actor=None,
    tank_client=None,
) -> dict[str, Any]:
    """Production paid path after free steps: Tank research, brain for gaps only.

    Code skill, memory recall and cache already ran in the memory bracket.
    Costs and tokens come from the research receipt (per-run, never cumulative).
    paid_run_id is only forwarded when set so existing callables keep working.
    """
    from core.research_adapter import research_web

    # Free steps (code skill, memory recall, cache) already ran in the memory
    # bracket around this call. Mark Base-style free-first; Tank is the paid route.
    brain_meta: dict[str, Any] = {
        "enabled": brain_enabled(),
        "free_first": True,
        "code_first": True,
    }
    kwargs: dict[str, Any] = {}
    if paid_run_id is not None:
        kwargs["paid_run_id"] = paid_run_id
    researched = await research_web(str(tenant_id), question, **kwargs)
    gap_receipt = None
    # None is a proven pre-send gap, never a researcher 503/timeout. Unknown
    # completion propagates without authorizing another paid delegation.
    # Plain unsigned tasks never acquire personal brain authority. Identity is
    # supplied only by the verified request or the durable enqueue actor.
    if researched is None and brain_enabled() and actor is not None:
        try:
            gap = await post_task(actor=actor, run_id=str(paid_run_id or uuid4()),
                task_key=str(task_id or "market.research"), payload={"question": question},
                tank_client=tank_client)
            gap_receipt = gap["receipt"]
            brain_meta.update(gap=True, result=gap["result"])
        except Exception as exc:
            # No prompt/provider body in errors; a failed delegation never
            # becomes a successful answer or a free receipt.
            brain_meta.update(error=type(exc).__name__, gap=True)
    if researched is None:
        return {
            "cost_usd": gap_receipt["cost_usd"] if gap_receipt else None,
            "tokens_in": gap_receipt["tokens_in"] if gap_receipt else 0,
            "tokens_out": gap_receipt["tokens_out"] if gap_receipt else 0,
            "paid_calls": 1 if gap_receipt else 0,
            "result": {"facts": [], "status": "unavailable", "brain": brain_meta, "questions": [question],
                       "receipts": [gap_receipt] if gap_receipt else []},
        }
    sources = [
        str(s.get("url") or s.get("href") or s) if isinstance(s, dict) else str(s)
        for s in (researched.get("sources") or researched.get("citations") or [])
    ]
    return {
        "cost_usd": None if researched.get("cost_usd",0) is None else float(researched.get("cost_usd",0)),
        "tokens_in": sum(int(r.get("tokens_in") or 0) for r in researched.get("receipts", [])),
        "tokens_out": sum(int(r.get("tokens_out") or 0) for r in researched.get("receipts", [])),
        "result": {
            **researched,
            "brain": brain_meta,
            "questions": list(researched.get("questions") or [question]),
            "trusted_sources": sources or ["tank-research"],
            **({'rejected_sources':list(researched['rejected_sources'])} if researched.get('rejected_sources') else {}),
            "reports": (
                [str(researched["report_id"])]
                if researched.get("report_id")
                else list(researched.get("reports") or [researched.get("answer") or "\n".join(f["text"] for f in researched.get("facts", []))])
            ),
            **({'watchlists':list(researched['watchlists'])} if researched.get('watchlists') else {}),
        },
    }
