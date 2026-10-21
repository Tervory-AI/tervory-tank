"""Policy-gated Perplexity presets through LiteLLM, with itemized research receipts.

Provider contract checked 2026-10-21:
https://docs.perplexity.ai/docs/agent-api/presets
https://docs.perplexity.ai/docs/getting-started/pricing
https://docs.litellm.ai/docs/providers/perplexity
No provider key, provider URL, arbitrary model, or policy write belongs here.
"""
from __future__ import annotations

import hmac
import json
import os
import re
import time
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
import controls
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

PRESETS = {f"research-{name}": name for name in ("fast", "low", "medium", "high")}
TASK = "market.research"
PRICE_DATE = "2026-10-21"
FEE_TYPES = {"search_web": "perplexity.search.fast", "fetch_url": "perplexity.fetch"}
MARKER = re.compile(r"\[([a-z_]+):(\d+)\]")


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: uuid.UUID
    question: str = Field(min_length=1, max_length=64000)
    preset: Literal["fast", "low", "medium", "high"] | None = None
    home_region: str | None = None


def amount(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError("missing cost")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid cost") from None
    if not result.is_finite() or result < 0:
        raise ValueError("invalid cost")
    return result


def provider_total(data: dict[str, Any]) -> Decimal:
    cost = (data.get("usage") or {}).get("cost")
    # LiteLLM normalizes Perplexity's cost object to its total_cost scalar.
    # Never add a tool fee to that total again, or trust the proxy's token estimate.
    if isinstance(cost, dict):
        if cost.get("currency", "USD") != "USD":
            raise ValueError("unsupported currency")
        cost = cost.get("total_cost")
    return amount(cost)


def receipt_costs(data: dict[str, Any], rates: dict[str, Decimal]) -> dict[str, Any]:
    usage = data.get("usage") or {}
    total = provider_total(data)
    calls = usage.get("tool_calls_details")
    if not isinstance(calls, dict):
        raise ValueError("missing tool usage")
    fees: dict[str, Decimal] = {"search_web": Decimal(0), "fetch_url": Decimal(0)}
    counts: dict[str, int] = {}
    for tool, detail in calls.items():
        if tool not in FEE_TYPES or not isinstance(detail, dict):
            raise ValueError("unsupported tool usage")
        count = detail.get("invocation")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("invalid tool usage")
        counts[tool] = count
        fees[tool] = count * rates[tool]
    cost = usage.get("cost")
    basis = "provider total minus price-book tool fees"
    if isinstance(cost, dict):
        # Preserve the provider breakdown when a gateway version passes it through.
        details = cost.get("tool_calls_cost_details")
        if isinstance(details, dict) and details:
            if set(details) - set(FEE_TYPES):
                raise ValueError("unsupported tool charges")
            fees = {tool: amount(details.get(tool, 0)) for tool in FEE_TYPES}
            basis = "provider breakdown"
        if cost.get("tool_calls_cost") is not None:
            if amount(cost["tool_calls_cost"]) != sum(fees.values()):
                raise ValueError("tool charges disagree with price book")
    token_cost = total - sum(fees.values())
    if token_cost < 0:
        raise ValueError("tool charges exceed provider total")
    return {
        "token_cost_usd": token_cost, "search_fee_usd": fees["search_web"],
        "fetch_fee_usd": fees["fetch_url"], "cost_usd": total,
        "cost_basis": basis, "tool_calls": counts, "price_date": PRICE_DATE,
        "lines": [
            {"label": "Tokens", "cost_usd": token_cost},
            {"label": "Search", "cost_usd": fees["search_web"]},
            {"label": "Source pages", "cost_usd": fees["fetch_url"]},
        ],
    }


def answer_sources(data: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    text: list[str] = []
    sources: dict[str, dict[str, str]] = {}
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message" and item.get("role") == "assistant":
            text.extend(part["text"] for part in item.get("content", [])
                        if isinstance(part, dict) and part.get("type") == "output_text"
                        and isinstance(part.get("text"), str))
        if item.get("type") != "search_results":
            continue
        for row in item.get("results") or []:
            if not isinstance(row, dict):
                continue
            source_id = row.get("id")
            if isinstance(source_id, bool) or not isinstance(source_id, int) or source_id < 1:
                continue
            url = row.get("url")
            if not isinstance(url, str):
                continue
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                continue
            marker = f"[{row.get('source') or 'web'}:{source_id}]"
            source = {"marker": marker, "url": url, "title": str(row.get("title") or "")}
            if marker in sources and sources[marker]["url"] != url:
                raise ValueError("ambiguous source marker")
            sources[marker] = source
    content = "\n".join(text).strip()
    markers = list(dict.fromkeys(match.group(0) for match in MARKER.finditer(content)))
    if not content or not markers or any(marker not in sources for marker in markers):
        raise ValueError("research answer has missing source evidence")
    return content, [sources[marker] for marker in markers]


def register(app: Any, runtime: dict[str, Any]) -> None:
    """Only registration touches main.py; its policy and region checks are reused."""
    router = APIRouter(prefix="/v1/research")

    async def authenticate(x_tank_key: str = Header(default="")) -> None:
        # A narrow additional corridor for Market Lab. Other room and homes keys
        # retain their existing restrictions; require_key is not broadened.
        candidates = (runtime["TANK_API_KEY"], os.environ.get("TANK_KEY_MARKET_LAB", ""))
        if x_tank_key and any(key.strip() and hmac.compare_digest(x_tank_key.encode(), key.encode())
                              for key in candidates):
            return
        raise HTTPException(status_code=401, detail="missing or invalid research key")

    async def allowed(req: ResearchRequest) -> tuple[dict[str, Any], str, str]:
        box = runtime["box_region"]()
        refused = runtime["home_region_refusal"](runtime["call_home"](req.home_region, box), box)
        if refused:
            raise HTTPException(status_code=403, detail=refused)
        policy = await runtime["load_policy"](TASK, req.tenant_id)
        model = policy["model"]
        # Merely adding a roster/candidate never enables a research call.
        if model not in PRESETS or not policy.get("promoted_at") or policy.get("auto_promote", True):
            raise HTTPException(status_code=409, detail="research preset has not been promoted by the founder")
        if req.preset is not None and req.preset != PRESETS[model]:
            raise HTTPException(status_code=409, detail="preset does not match the promoted policy")
        sent = "\n".join([str(policy.get("system_prompt") or ""), req.question])
        refused = runtime["model_call_refusal"](sent, model, box=box, tenant_id=str(req.tenant_id))
        if refused:
            raise HTTPException(status_code=403, detail=refused)
        return policy, model, box

    async def rates() -> dict[str, Decimal]:
        async with runtime["pool"]().acquire() as conn:
            rows = await conn.fetch(
                """SELECT DISTINCT ON (outcome_type) outcome_type, unit_price
                   FROM tank.price_book WHERE tenant_id=$1 AND outcome_type=ANY($2::text[])
                     AND currency='USD' AND effective_from <= now()
                     AND (effective_to IS NULL OR effective_to > now())
                   ORDER BY outcome_type, effective_from DESC""",
                runtime["PLATFORM_TENANT"], list(FEE_TYPES.values()),
            )
        try:
            found = {row["outcome_type"]: amount(row["unit_price"]) for row in rows}
        except ValueError:
            raise HTTPException(status_code=503, detail="research price book is invalid") from None
        if not set(FEE_TYPES.values()) <= set(found):
            raise HTTPException(status_code=503, detail="research price book is incomplete")
        return {tool: found[kind] for tool, kind in FEE_TYPES.items()}

    async def record(req: ResearchRequest, model: str, box: str, data: dict[str, Any],
                     elapsed: int, costs: dict[str, Any] | None, sources: list[dict[str, str]],
                     error: str | None) -> uuid.UUID:
        ledger_id = uuid.uuid4()
        try:
            total: Decimal | None = provider_total(data)
        except (ValueError, AttributeError):
            total = None
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        def tokens(key: str) -> int:
            value = usage.get(key)
            return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 2**31 else 0
        async with runtime["pool"]().acquire() as conn:
            await conn.execute(
                """INSERT INTO tank.ledger
                   (id,tenant_id,region,agent,task_type,rung,model,tokens_in,tokens_out,
                    cost_usd,latency_ms,outcome,error,token_cost_usd,search_fee_usd,
                    fetch_fee_usd,provider_cost_usd,research_sources,research_cost_status)
                   VALUES ($1,$2,$3,'market_lab','market.research',1,$4,$5,$6,$7,$8,$9,$10,
                           $11,$12,$13,$14,$15::jsonb,$16)""",
                ledger_id, req.tenant_id, box, model, tokens("input_tokens"), tokens("output_tokens"),
                total if total is not None else Decimal(0), elapsed, "failed" if error else "delivered", error,
                costs["token_cost_usd"] if costs else None, costs["search_fee_usd"] if costs else None,
                costs["fetch_fee_usd"] if costs else None, total, json.dumps(sources),
                "itemized" if costs else "unitemized" if total is not None else "unknown",
            )
        return ledger_id

    @router.post("/status", dependencies=[Depends(authenticate)])
    async def status(req: ResearchRequest) -> dict[str, Any]:
        _, model, _ = await allowed(req)
        return {"enabled": True, "preset": PRESETS[model]}

    @router.post("", dependencies=[Depends(authenticate)])
    async def research(req: ResearchRequest) -> dict[str, Any]:
        policy, model, box = await allowed(req)
        await controls.refuse_paid(task=TASK, path="research")
        prices = await rates()  # Fail before spending if the fee schedule is unavailable.
        payload = {"model": model, "input": req.question,
                   "max_output_tokens": policy["max_tokens_out"], "stream": False,
                   "fallbacks": []}  # No cross-preset escape from the tenant's allow-list.
        if policy.get("system_prompt"):
            payload["instructions"] = policy["system_prompt"]
        started = time.perf_counter()
        data: dict[str, Any] = {}
        costs = None
        sources: list[dict[str, str]] = []
        error = None
        content = ""
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(
                    runtime["LITELLM_URL"].rstrip("/") + "/v1/responses",
                    headers={"Authorization": f"Bearer {runtime['LITELLM_MASTER_KEY']}"}, json=payload,
                )
            parsed = response.json()
            if not isinstance(parsed, dict):
                raise ValueError("invalid response")
            data = parsed
            if response.status_code != 200 or data.get("status") != "completed":
                raise ValueError("research provider did not complete")
            costs = receipt_costs(data, prices)
            content, sources = answer_sources(data)
        except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError):
            # Never echo provider error bodies, prompts, credentials or response URLs.
            error = "Research failed or its sources and costs could not be verified."
        elapsed = int((time.perf_counter() - started) * 1000)
        ledger_id = await record(req, model, box, data, elapsed, costs, sources, error)
        if error:
            raise HTTPException(status_code=502, detail={"ledger_id": str(ledger_id), "message": error})
        wire_receipt = json.loads(json.dumps({**costs, "sources": sources}, default=float))
        return {"ledger_id": str(ledger_id), "model": model, "preset": PRESETS[model],
                "content": content, "sources": sources, "cost_usd": float(costs["cost_usd"]),
                "receipt": wire_receipt}

    app.include_router(router)
