"""The template agent: a ping job and a five-minute heartbeat.

Copy this folder to start a new Squad member. It knows no industry.
"""

from __future__ import annotations

import os

from chassis.app import create_app
from chassis.jobs import JobContext

AGENT = os.environ.get("AGENT_NAME", "template")
# Platform tenant. The heartbeat is the box checking itself, not a client's work.
HEARTBEAT_TENANT = "00000000-0000-0000-0000-000000000001"


async def ping(ctx: JobContext) -> dict:
    return {"pong": True, "agent": ctx.agent}


app = create_app(
    agent=AGENT,
    handlers={"ping": ping},
    schedules=[
        {
            "tenant_id": HEARTBEAT_TENANT,
            "cron": "*/5 * * * *",
            "kind": "ping",
            "input": {"heartbeat": True},
        }
    ],
)
