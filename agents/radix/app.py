"""Radix: the security auditor. A ping job, a five-minute heartbeat, and code scans.

Scans run on a tarball or git bundle the caller hands over. Outbound HTTP other
than Tank and Hermes goes through net.py. A scan does not use it.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from chassis.app import create_app
from chassis.jobs import JobContext
from chassis.logs import log_line
from scanlib.orchestrate import scan_job
from verify.routes import attach as attach_verification
from gold_sources import attach as attach_gold

AGENT = os.environ.get("AGENT_NAME", "radix")
# Platform tenant. The heartbeat is the box checking itself, not a client's work.
HEARTBEAT_TENANT = "00000000-0000-0000-0000-000000000001"

log = logging.getLogger("agent")


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


async def scan(ctx: JobContext) -> dict:
    result = await scan_job(ctx)
    # Counts only. The finding text can carry a file path, never a secret value.
    log_line(AGENT, "scan finished", tenant_id=str(ctx.tenant_id), job_id=str(ctx.job_id))
    return result


app = create_app(
    agent=AGENT,
    handlers={"ping": ping, "scan": scan},
    schedules=[
        {
            "tenant_id": HEARTBEAT_TENANT,
            "cron": "*/5 * * * *",
            "kind": "ping",
            "input": {"heartbeat": True},
        }
    ],
)

attach_verification(app)
attach_gold(app)

from passive_routes import attach as attach_passive
attach_passive(app)
