"""Ghost's room: private state, fixed probes, authenticated entry points."""
from __future__ import annotations

import asyncio
import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import advisories as advisory_watch
from . import inventory as inv
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

    async def record(self, receipt_id: str, step: str, outcome: str, task_type: str = "ghost.incident") -> None:
        if task_type not in {"ghost.incident", "ghost.advisory"}:
            raise ValueError("Unknown Ghost receipt type.")
        result = await self.call("POST", "/v1/ledger/vendor", {
            "id": receipt_id, "tenant_id": PLATFORM_TENANT, "agent": "ghost",
            "task_type": task_type, "vendor": "ghost." + step, "units": 1,
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


async def refresh_inventory(app: FastAPI) -> dict:
    """Coolify (read-only, only when its token is set) and our own sites' headers."""
    store, http = app.state.store, app.state.http
    seen = advisory_watch.iso(advisory_watch.now_utc())
    result: dict = {}
    try:
        components = await inv.fetch_coolify(http)
        if components is None:
            result["coolify"] = "not_connected"
        else:
            store.replace_inventory(PLATFORM_TENANT, "coolify", [vars(c) for c in components], seen)
            result["coolify"] = "ok"
    except Exception:
        result["coolify"] = "unavailable"
    headers: list = []
    failed = 0
    for app_name, host in inv.WATCHED_SITES.items():
        try:
            headers.extend(await inv.fetch_headers(http, app_name, host))
        except Exception:
            failed += 1
    if headers:
        store.replace_inventory(PLATFORM_TENANT, "headers", [vars(c) for c in headers], seen)
    result["headers"] = "ok" if not failed else f"{len(inv.WATCHED_SITES) - failed}_of_{len(inv.WATCHED_SITES)}"
    store.set_state(PLATFORM_TENANT, "inventory_refreshed", {"at": seen, **result})
    return result


async def nightly(app: FastAPI) -> None:
    while True:
        last = app.state.store.get_state(PLATFORM_TENANT, "inventory_refreshed", {}).get("at")
        moment = advisory_watch.parse_time(last)
        if moment is None or (advisory_watch.now_utc() - moment).total_seconds() > 86400:
            try:
                async with app.state.advisory_lock:
                    await refresh_inventory(app)
            except Exception:
                pass
        await asyncio.sleep(1800)


async def bounded_json(request: Request, limit: int) -> bytes:
    raw = await request.body()
    if len(raw) > limit:
        raise HTTPException(413, "Request too large.")
    return raw


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not os.environ.get("TANK_KEY"):
            raise RuntimeError("Ghost's Tank key is not configured.")
        store = Store(Path(os.environ.get("DATA_DIR", "/data")) / "ghost.sqlite3", os.environ.get("TANK_REGION", "us-east"))
        async with httpx.AsyncClient(follow_redirects=False) as http:
            tank = Tank(http)
            app.state.store = store
            app.state.probes = Probes(http, tank, os.environ["TANK_KEY"])
            app.state.investigator = Investigator(store, app.state.probes, tank)
            app.state.lock = asyncio.Lock()
            app.state.monitor = {"running": False, "unavailable_checks": 0}
            app.state.http = http
            app.state.advisory_lock = asyncio.Lock()
            app.state.watcher = advisory_watch.Watcher(store, advisory_watch.Feeds(http), tank)
            tasks = [asyncio.create_task(watch(app)), asyncio.create_task(nightly(app)),
                     asyncio.create_task(advisory_watch.watch(app))]
            try:
                yield
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
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

    # ---------- GHOST-2: inventory and advisory watcher ----------

    @app.post("/ghost/inventory/report", dependencies=[Depends(require_tank)])
    async def inventory_report(request: Request):
        """Host and repo facts arrive here (Ghost has no Docker socket). Replaces that source's snapshot."""
        raw = await bounded_json(request, 2_000_000)
        try:
            report = inv.InventoryReport.model_validate_json(raw)
            components = report.to_components()
        except ValueError:
            raise HTTPException(422, "Invalid Ghost request.") from None
        if not components:
            raise HTTPException(422, "The report has no version facts.")
        seen = advisory_watch.iso(advisory_watch.now_utc())
        async with app.state.advisory_lock:
            stored = app.state.store.replace_inventory(PLATFORM_TENANT, report.source, [vars(c) for c in components], seen)
        return {"accepted": True, **stored}

    @app.get("/ghost/inventory", dependencies=[Depends(require_tank)])
    async def inventory_list(history: bool = False):
        return {"components": app.state.store.inventory(PLATFORM_TENANT, current_only=not history),
                "refreshed": app.state.store.get_state(PLATFORM_TENANT, "inventory_refreshed")}

    @app.post("/ghost/inventory/refresh", dependencies=[Depends(require_tank)])
    async def inventory_refresh():
        """Called after each deploy (deploy-on-merge receipt); also runs nightly."""
        async with app.state.advisory_lock:
            return await refresh_inventory(app)

    @app.post("/ghost/advisories/pull", dependencies=[Depends(require_tank)])
    async def advisories_pull():
        async with app.state.advisory_lock:
            return await app.state.watcher.cycle()

    @app.get("/ghost/advisories/matches", dependencies=[Depends(require_tank)])
    async def advisory_matches(state: str = Query(default="open", pattern="^(open|resolved|all)$")):
        rows = app.state.store.matches(PLATFORM_TENANT, None if state == "all" else state)
        return {"matches": rows, "last_cycle": app.state.store.get_state(PLATFORM_TENANT, "last_cycle")}

    return app


app = create_app()
