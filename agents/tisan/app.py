"""Tisan: the developer and designer. A ping job, a five-minute heartbeat, the project scaffold, and the Figma reader."""

from __future__ import annotations

import importlib.util
import hashlib
import logging
import os
from pathlib import Path
from typing import Any

from chassis.app import create_app
from chassis.jobs import JobContext

AGENT = os.environ.get("AGENT_NAME", "tisan")
# Platform tenant. The heartbeat is the box checking itself, not a client's work.
HEARTBEAT_TENANT = "00000000-0000-0000-0000-000000000001"

log = logging.getLogger("agent")
_scaffold = None
_figma = None


def _load_beside(cache: dict[str, Any], key: str, filename: str) -> Any:
    if key in cache:
        return cache[key]
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(key, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"{filename} is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cache[key] = module
    return module


def _scaffold_module():
    """Load the scaffold from beside this file. The image copies both to /app."""
    global _scaffold
    if _scaffold is None:
        _scaffold = {}
    return _load_beside(_scaffold, "tisan_scaffold", "scaffold.py")


async def ping(ctx: JobContext) -> dict:
    result: dict = {"pong": True, "agent": ctx.agent}
    if ctx.input.get("heartbeat"):
        # The same text every time, so Hermes folds it into one memory and
        # counts it (seen). A Hermes outage must not fail the heartbeat.
        try:
            saved = await ctx.memory.remember(
                ctx.tenant_id,
                f"{ctx.agent} heartbeat",
                "heartbeat",
                "schedule:*/5",
            )
            result["heartbeats_seen"] = saved.get("seen")
        except Exception as exc:  # noqa: BLE001 — class name only, never the message
            log.warning("heartbeat memory failed (%s)", type(exc).__name__)
            result["memory"] = "unreachable"
    return result


async def scaffold(ctx: JobContext) -> dict:
    """Build one site for this job's tenant. The tenant comes from the job, not the brief."""
    module = _scaffold_module()
    result = await module.execute(ctx.input, str(ctx.tenant_id))
    if result.get("ok") is True and result.get("slug"):
        from chassis.events import publish
        await publish(str(ctx.tenant_id), "tisan.build.ready", str(ctx.job_id), {
            "job_id": str(ctx.job_id), "site_id": hashlib.sha256(result["slug"].encode()).hexdigest()})
    return result


async def figma(ctx: JobContext) -> dict:
    """Read the recorded Figma page for this job's tenant. No call leaves the room."""
    module = _load_beside(_figma_cache(), "tisan_figma", "figma.py")
    return await module.execute(ctx.input, str(ctx.tenant_id))


def _figma_cache() -> dict[str, Any]:
    global _figma
    if _figma is None:
        _figma = {}
    return _figma


# Ten minutes for a site build. Ping and every other agent stay on the chassis default.
SCAFFOLD_TIMEOUT_S = 600

app = create_app(
    agent=AGENT,
    handlers={"ping": ping, "scaffold": scaffold, "figma": figma},
    job_timeouts={"scaffold": SCAFFOLD_TIMEOUT_S},
    schedules=[
        {
            "tenant_id": HEARTBEAT_TENANT,
            "cron": "*/5 * * * *",
            "kind": "ping",
            "input": {"heartbeat": True},
        }
    ],
)

# Room-only export of previously approved frame/page pairs.
_load_beside({}, "tisan_gold_sources", "gold_sources.py").mount(app)


from fastapi import Header, HTTPException
from pydantic import BaseModel, Field
from uuid import UUID
import hmac


class EvalCase(BaseModel):
    skill_id: str
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    tenant_id: UUID
    input: dict[str, Any]


@app.post("/evals/run")
async def eval_case(body: EvalCase, x_tank_key: str = Header(default="")) -> dict:
    key = os.environ.get("TANK_KEY", "")
    if not key or not hmac.compare_digest(key, x_tank_key):
        raise HTTPException(401, "room key required")
    if body.skill_id == "tisan.figma":
        module = _load_beside(_figma_cache(), "tisan_figma", "figma.py")
    elif body.skill_id == "tisan.scaffold":
        module = _scaffold_module()
    else:
        raise HTTPException(404, "unknown eval skill")
    try:
        return await module.execute(body.input, str(body.tenant_id))
    except ValueError:
        return {"refused": True, "error": "invalid eval input"}
