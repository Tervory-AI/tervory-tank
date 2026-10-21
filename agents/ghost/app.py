"""Ghost's room: private state, fixed probes, authenticated entry points."""
from __future__ import annotations

import asyncio
import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .gold_sources import candidates
from .investigate import Investigator
from .models import Look, Message, Observation, PLATFORM_TENANT, Resolution, SITES, ROOMS, Signal, classify_message
from .probes import Probes
from .store import Store


async def require_tank(x_tank_key: str = Header(default="")) -> None:
    expected = os.environ.get("TANK_KEY", "")
    if not expected or not hmac.compare_digest(expected.encode(), x_tank_key.encode()):
        raise HTTPException(404, "Not found.")


class Tank:
    def __init__(self, http: httpx.AsyncClient):
        self.http = http

    async def call(self, method: str, path: str, body: dict | None = None) -> dict:
        key = os.environ.get("TANK_KEY", "")
        if not key:
            raise RuntimeError("Ghost's Tank key is not configured.")
        try:
            response = await self.http.request(method, "http://tank:8000" + path,
                                               headers={"X-Tank-Key": key}, json=body, timeout=45)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError("Invalid response")
            return result
        except (httpx.HTTPError, ValueError):
            raise RuntimeError("Tank did not accept the request.") from None

    async def record(self, receipt_id: str, step: str, outcome: str) -> None:
        result = await self.call("POST", "/v1/ledger/vendor", {
            "id": receipt_id, "tenant_id": PLATFORM_TENANT, "agent": "ghost",
            "task_type": "ghost.incident", "vendor": "ghost." + step, "units": 1,
            "cost_usd": 0, "outcome": outcome, "region": os.environ.get("TANK_REGION", "us-east"),
        })
        if result.get("recorded") is not True or result.get("ledger_id") != receipt_id:
            raise RuntimeError("Tank did not record the receipt.")


async def watch(app: FastAPI) -> None:
    while True:
        failures = 0
        for target in (*SITES, *ROOMS, "tank"):
            signals = (Signal.health, Signal.slow, Signal.dns, Signal.certificate, Signal.headers) if target in SITES else (Signal.health,)
            for signal in signals:
                try:
                    async with app.state.lock:
                        observation = await app.state.probes.reproduce(Look(target=target, signal=signal))
                        await app.state.investigator.alert(observation)
                except Exception:
                    failures += 1
        app.state.monitor = {"running": True, "unavailable_checks": failures}
        await asyncio.sleep(300)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not os.environ.get("TANK_KEY"):
            raise RuntimeError("Ghost's Tank key is not configured.")
        store = Store(Path(os.environ.get("DATA_DIR", "/data")) / "ghost.sqlite3")
        async with httpx.AsyncClient(follow_redirects=False) as http:
            tank = Tank(http)
            app.state.store = store
            app.state.probes = Probes(http, tank, os.environ["TANK_KEY"])
            app.state.investigator = Investigator(store, app.state.probes, tank)
            app.state.lock = asyncio.Lock()
            app.state.monitor = {"running": False, "unavailable_checks": 0}
            task = asyncio.create_task(watch(app))
            try:
                yield
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                store.close()

    app = FastAPI(title="Ghost", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(_request, _error):
        # Pydantic's default errors include the rejected input (possibly a secret).
        return JSONResponse(status_code=422, content={"detail": "Invalid Ghost request."})

    @app.exception_handler(RuntimeError)
    async def unavailable(_request, _error):
        return JSONResponse(status_code=503, content={"detail": "A required service is unavailable. No production action was taken."})

    @app.get("/health")
    async def health():
        return {"ok": hasattr(app.state, "store"), "agent": "ghost"}

    @app.get("/incidents", dependencies=[Depends(require_tank)])
    async def incidents():
        return {"incidents": app.state.store.list(PLATFORM_TENANT), "monitor": app.state.monitor,
                "integrations": {"brain": "awaiting_agent_1", "bucket": "awaiting_bucket_1",
                                 "workers": "founder_approval_required", "logs_ci_deploys": "awaiting_read_only_feed"}}

    @app.post("/look", dependencies=[Depends(require_tank)])
    async def look(body: Look):
        async with app.state.lock:
            return await app.state.investigator.look(body)

    @app.post("/message", dependencies=[Depends(require_tank)])
    async def message(body: Message):
        async with app.state.lock:
            return await app.state.investigator.look(classify_message(body.text), "message")

    @app.post("/alert", dependencies=[Depends(require_tank)])
    async def alert(body: Observation):
        async with app.state.lock:
            return {"incident": await app.state.investigator.alert(body)}

    @app.post("/incidents/{incident}/resolve", dependencies=[Depends(require_tank)])
    async def resolve(incident: UUID, body: Resolution):
        try:
            async with app.state.lock:
                return await app.state.investigator.resolve(str(incident), body)
        except LookupError:
            raise HTTPException(404, "Issue not found.") from None
        except ValueError:
            raise HTTPException(409, "The original check must pass before solving the issue.") from None

    @app.get("/gold/candidates", dependencies=[Depends(require_tank)])
    async def gold(limit: int = Query(default=200, ge=1, le=200)):
        return candidates(app.state.store, os.environ.get("TANK_REGION", "us-east"), limit)

    return app


app = create_app()
