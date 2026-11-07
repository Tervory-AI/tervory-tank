"""Opli product FastAPI app: chassis MemoryClient + live memory/code routes.

create_app wires app.state.memory to chassis MemoryClient (Hermes
POST /memories, POST /recall, GET /records, DELETE /memories/{id} with Opli's
agent key TANK_KEY_OPLI) and app.state.command to Tank's command module.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from agents.opli.gates_memory import production_memory
from memory_api import attach_opli_live_routes


def create_app(*, command: Any = None, memory: Any = None, http: Any = None) -> FastAPI:
    """Build the live Opli app. ``memory`` defaults to chassis MemoryClient."""
    app = FastAPI(title="opli")
    if memory is None:
        memory = production_memory(http=http)
    app.state.memory = memory
    app.state.command = command
    attach_opli_live_routes(app)
    return app


__all__ = ["create_app"]
