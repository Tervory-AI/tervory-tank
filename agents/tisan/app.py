"""Tisan: the developer and designer. A ping job, a five-minute heartbeat, and the project scaffold."""

from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path

from chassis.app import create_app
from chassis.jobs import JobContext

AGENT = os.environ.get("AGENT_NAME", "tisan")
# Platform tenant. The heartbeat is the box checking itself, not a client's work.
HEARTBEAT_TENANT = "00000000-0000-0000-0000-000000000001"

log = logging.getLogger("agent")
_scaffold = None


def _scaffold_module():
    """Load the scaffold from beside this file. The image copies both to /app."""
    global _scaffold
    if _scaffold is not None:
        return _scaffold
    path = Path(__file__).resolve().parent / "scaffold.py"
    spec = importlib.util.spec_from_file_location("tisan_scaffold", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("scaffold is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _scaffold = module
    return module


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
    return await module.execute(ctx.input, str(ctx.tenant_id))


# Ten minutes for a site build. Ping and every other agent stay on the chassis default.
SCAFFOLD_TIMEOUT_S = 600

app = create_app(
    agent=AGENT,
    handlers={"ping": ping, "scaffold": scaffold},
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
