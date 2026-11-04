"""Provisioned Hermes runtimes, without a task API or pipeline caller.

Tiger's extraction stays code; Zenas keeps its existing civil-only tools.
Starting either optional container
does not authorize model work; a future escalation needs its own implementation.
"""

import os

from fastapi import FastAPI

ROOM = os.environ.get("BRAIN_ROOM", "tiger")
if ROOM not in {"tiger", "zenas"}:
    raise ValueError("Unsupported standby room")

app = FastAPI()


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "room": ROOM, "hermes_version": "0.22.2"}
