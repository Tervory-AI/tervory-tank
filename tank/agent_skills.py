"""Base's Hermes boundary: room authentication, chat receipts and Skala exchange.

There is deliberately no second skill runner or approval endpoint here.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import time
import uuid
from pathlib import Path
from typing import Any, Literal

import httpx
import yaml
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

ROOM = "base"
SUBMISSIONS = Path("/tmp/tervory-agent-skills")
LEDGER_SQL = """
INSERT INTO tank.ledger
 (id,tenant_id,region,agent,task_type,rung,model,priority,tokens_in,tokens_out,
  cost_usd,latency_ms,outcome,task_id,error)
VALUES ($1,$2,$3,'base','agent.base.think',$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
"""


def room_key(room: str, authorization: str = "", x_tank_key: str = "") -> None:
    """Only Base is piloting. Never accept the Workspace or another room's key."""
    if room != ROOM:
        raise HTTPException(403, "This room does not have a brain pilot.")
    bearer = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
    if bearer and x_tank_key and not hmac.compare_digest(bearer.encode(), x_tank_key.encode()):
        raise HTTPException(401, "Conflicting room keys.")
    presented = bearer or x_tank_key
    expected = os.environ.get("TANK_KEY_BASE", "").strip()
    if not expected or not presented or not hmac.compare_digest(expected.encode(), presented.encode()):
        raise HTTPException(401, "Base room key required.")


def local_region(tank: Any, home: str | None) -> str:
    box = tank.box_region()
    # The Base pilot is US-only. Never forward a ZA tenant to Boston.
    if box != "us-east" or (home is not None and home != box):
        raise HTTPException(403, "Base's pilot stays in its home region.")
    return box


class Chat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = "policy"
    messages: list[dict[str, Any]] = Field(min_length=1, max_length=512)
    tools: list[dict[str, Any]] | None = Field(default=None, max_length=64)
    tool_choice: str | dict[str, Any] | None = None
    parallel_tool_calls: bool | None = None
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    max_completion_tokens: int | None = Field(default=None, ge=1, le=32768)
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, gt=0, le=1)
    stop: str | list[str] | None = None
    stream: bool = False
    stream_options: dict[str, Any] | None = None
    response_format: dict[str, Any] | None = None
    reasoning_effort: str | None = None
    user: str | None = None
    n: Literal[1] = 1


def validate_chat(body: Chat) -> None:
    if len(json.dumps(body.model_dump())) > 1_000_000:
        raise HTTPException(413, "Conversation is too large.")
    for message in body.messages:
        if message.get("role") not in {"system", "developer", "user", "assistant", "tool"}:
            raise HTTPException(422, "Unsupported message role.")
        content = message.get("content")
        if content is not None and not isinstance(content, str):
            if not isinstance(content, list) or any(
                not isinstance(p, dict) or p.get("type") != "text" or not isinstance(p.get("text"), str)
                for p in content
            ):
                raise HTTPException(422, "The Base pilot accepts text only.")


def amount(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("Missing usage cost") from None
    if not math.isfinite(number) or number < 0:
        raise ValueError("Invalid usage cost")
    return number


def baseline_cost(roster: list[dict], model: str, tokens_in: int, tokens_out: int) -> float | None:
    for row in roster:
        if row.get("model_name") == model:
            info = row.get("model_info") or {}
            try:
                return tokens_in * amount(info.get("input_cost_per_token")) + tokens_out * amount(info.get("output_cost_per_token"))
            except ValueError:
                return None
    return None


async def complete(tank: Any, body: Chat, tenant: uuid.UUID, task: uuid.UUID | None, region: str) -> dict:
    validate_chat(body)
    policy = await tank.load_policy("agent.base.think", tenant)
    model = policy["model"]
    if tank.graduate.router_cannot_serve(model):
        raise HTTPException(409, "The brain needs a model policy.")
    messages = list(body.messages)
    if policy.get("system_prompt"):
        messages.insert(0, {"role": "system", "content": policy["system_prompt"]})
    # Policy chooses the route; a model name in an SDK request cannot override it.
    payload = body.model_dump(exclude_none=True, exclude={"model", "stream", "stream_options", "max_completion_tokens", "user"})
    payload.update(model=model, messages=messages, stream=False,
                   max_tokens=min(body.max_tokens or body.max_completion_tokens or policy["max_tokens_out"], policy["max_tokens_out"]))
    ledger_id = uuid.uuid4()
    started = time.perf_counter()
    outcome, error, cost = "failed", "Model gateway unavailable.", 0.0
    tokens_in = tokens_out = 0
    answered = model
    data: dict[str, Any] = {}
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                tank.LITELLM_URL + "/v1/chat/completions", json=payload,
                headers={"Authorization": "Bearer " + tank.LITELLM_MASTER_KEY},
            )
        if response.status_code == 200:
            data = response.json()
            usage = data["usage"]
            tokens_in, tokens_out = int(usage["prompt_tokens"]), int(usage["completion_tokens"])
            if tokens_in < 0 or tokens_out < 0 or not isinstance(data["choices"][0]["message"], dict):
                raise ValueError("Malformed model response")
            cost = amount(response.headers.get("x-litellm-response-cost"))
            answered = response.headers.get("x-litellm-model-group") or model
            outcome, error = "delivered", None
        else:
            error = "Model gateway refused the call (HTTP %d)." % response.status_code
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        # Never return or log upstream bodies: they can contain credentials/prompts.
        error = "Model gateway failed or returned an incomplete receipt."
    latency = int((time.perf_counter() - started) * 1000)
    baseline = policy.get("baseline_model") or model
    baseline_usd = baseline_cost(await tank._roster_models(), baseline, tokens_in, tokens_out)
    receipt = {
        "ledger_id": str(ledger_id), "tenant_id": str(tenant), "task_id": str(task) if task else None,
        "room": ROOM, "task_type": "agent.base.think", "region": region, "model": answered,
        "cost_usd": cost, "baseline_model": baseline, "baseline_cost_usd": baseline_usd,
        "saving_usd": None if baseline_usd is None else baseline_usd - cost,
        "tokens_in": tokens_in, "tokens_out": tokens_out, "latency_ms": latency, "outcome": outcome,
    }
    async with tank.pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(LEDGER_SQL, ledger_id, tenant, region, policy["rung"], answered, policy["priority"],
                               tokens_in, tokens_out, cost, latency, outcome, task, error)
            await conn.execute(
                "INSERT INTO tank.agent_receipts (ledger_id,tenant_id,room,receipt) VALUES ($1,$2,'base',$3::jsonb)",
                ledger_id, tenant, json.dumps(receipt),
            )
    if outcome != "delivered":
        raise HTTPException(502, {"message": error, "receipt": receipt})
    return {
        "id": "chatcmpl-" + str(ledger_id), "object": "chat.completion", "created": int(time.time()),
        "model": answered, "choices": data["choices"],
        "usage": {"prompt_tokens": tokens_in, "completion_tokens": tokens_out, "total_tokens": tokens_in + tokens_out},
        "receipt": receipt,
    }


def stream_completion(result: dict):
    """Buffer upstream so spend is durable before the SDK sees any answer."""
    base = {k: result[k] for k in ("id", "created", "model")}
    base["object"] = "chat.completion.chunk"
    for choice in result["choices"]:
        delta = dict(choice["message"])
        if delta.get("tool_calls"):
            delta["tool_calls"] = [{"index": i, **tool} for i, tool in enumerate(delta["tool_calls"])]
        yield "data: " + json.dumps({**base, "choices": [{"index": choice.get("index", 0), "delta": delta, "finish_reason": None}]}) + "\n\n"
        yield "data: " + json.dumps({**base, "choices": [{"index": choice.get("index", 0), "delta": {}, "finish_reason": choice.get("finish_reason", "stop")}]}) + "\n\n"
    yield "data: " + json.dumps({**base, "choices": [], "usage": result["usage"], "receipt": result["receipt"]}) + "\n\n"
    yield "data: [DONE]\n\n"


def build_router(tank: Any) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/agents/{room}/chat/completions")
    async def chat(room: str, body: Chat, request: Request,
                   x_tenant_id: uuid.UUID = Header(), x_task_id: uuid.UUID | None = Header(default=None),
                   x_home_region: str | None = Header(default=None)):
        room_key(room, request.headers.get("authorization", ""), request.headers.get("x-tank-key", ""))
        result = await complete(tank, body, x_tenant_id, x_task_id, local_region(tank, x_home_region))
        if body.stream:
            return StreamingResponse(stream_completion(result), media_type="text/event-stream")
        return result

    return router
