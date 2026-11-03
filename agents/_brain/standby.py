"""Tiger's provisioned Hermes runtime, without a task API or pipeline caller.

Tiger's current extraction skills are code. Starting this optional container
does not authorize model work; a future escalation needs its own implementation.
"""

from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "room": "tiger", "hermes_version": "0.22.2"}
