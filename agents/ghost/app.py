"""Ghost's room: private state, fixed probes, authenticated entry points."""
from __future__ import annotations

import asyncio
import json
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
from . import shields as shield_room
from .gold_sources import candidates
from .investigate import Investigator
from .models import Look, Message, Observation, PLATFORM_TENANT, Resolution, SITES, ROOMS, Signal, classify_message
from .threat_payload import BURN_DETAIL, ThreatBurned, ThreatAction, accept_threat_payload, threat_to_shield_request
from .guardrails import GUARD_BURN_DETAIL, GuardBurned, guard_inbound_if_enabled
from . import wraith as wraith_room
from . import rails as airgap_rails
from . import watch_oss as watch_oss_room
from .watch_oss import AnomalyEvent, handoff_threat, propose_from_anomaly
from . import enforce_oss as enforce_oss_room
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
            raise RuntimeError("Autumbra Watch's Tank key is not configured.")
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
        if task_type not in {"ghost.incident", "ghost.advisory", "ghost.shield"}:
            raise ValueError("Unknown Autumbra Watch receipt type.")
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
            raise RuntimeError("Autumbra Watch's Tank key is not configured.")
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
            app.state.shields = shield_room.Shields(store, http, tank)
            tasks = [asyncio.create_task(watch(app)), asyncio.create_task(nightly(app)),
                     asyncio.create_task(advisory_watch.watch(app))]
            try:
                yield
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                store.close()

    app = FastAPI(title="Autumbra Watch", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(_request, _error):
        # Pydantic's default errors include the rejected input (possibly a secret).
        return JSONResponse(status_code=422, content={"detail": "Invalid Autumbra Watch request."})

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
            report = inv.InventoryReport.from_body(raw)
            components = report.to_components()
        except ValueError:
            raise HTTPException(422, "Invalid Autumbra Watch request.") from None
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
            summary = await app.state.watcher.cycle()
            if getattr(app.state, "shields", None) is not None:
                await app.state.shields.after_cycle()
            return summary

    @app.get("/ghost/advisories/matches", dependencies=[Depends(require_tank)])
    async def advisory_matches(state: str = Query(default="open", pattern="^(open|resolved|all)$")):
        rows = app.state.store.matches(PLATFORM_TENANT, None if state == "all" else state)
        return {"matches": rows, "last_cycle": app.state.store.get_state(PLATFORM_TENANT, "last_cycle")}

    # ---------- GHOST-2 D3: Shields Up (dry-run unless CLOUDFLARE_API_TOKEN_GHOST is set) ----------

    @app.get("/ghost/shields", dependencies=[Depends(require_tank)])
    async def shields_list():
        return {"mode": shield_room.mode(),
                "shields": [shield_room.public_view(s) for s in app.state.store.shields(PLATFORM_TENANT)]}

    @app.post("/ghost/triage/accept", dependencies=[Depends(require_tank)])
    async def triage_accept(request: Request):
        """Autumbra Dual-LLM air gap: optional guard (flag OFF), then ThreatPayload.

        Untrusted body hits guard_inbound_if_enabled first (no-op unless
        GHOST_GUARDRAILS_ENABLED / AUTUMBRA_GUARDRAILS_ENABLED=1), then
        accept_threat_payload. Burn on fail (422, fixed detail, never echo body).
        propose_shield only builds a dry-run/founder proposal — never raises a
        shield without the Shield tap. Watch has no weapons; Enforce stays behind
        the Enforce flag + founder tap.
        """
        raw = await bounded_json(request, 8_000)
        try:
            guard_inbound_if_enabled(raw)
            payload = accept_threat_payload(raw)
        except GuardBurned:
            raise HTTPException(422, GUARD_BURN_DETAIL) from None
        except ThreatBurned:
            raise HTTPException(422, BURN_DETAIL) from None
        if payload.action == ThreatAction.propose_shield:
            async with app.state.advisory_lock:
                try:
                    shield = await app.state.shields.propose(threat_to_shield_request(payload))
                except ValueError:
                    raise HTTPException(422, BURN_DETAIL) from None
            return {"accepted": True, "action": payload.action.value,
                    "shield": shield_room.public_view(shield),
                    "note": "Proposed only. Founder must tap Shield before anything changes."}
        # open_match / write_brief: acknowledge schema pass; no auto-execute in this spike.
        return {"accepted": True, "action": payload.action.value,
                "severity": payload.severity.value, "site": payload.site,
                "note": "Schema passed. No execute path for this action yet."}

    @app.post("/ghost/wraith/enforce", dependencies=[Depends(require_tank)])
    async def wraith_enforce(request: Request):
        """Autumbra Enforce stub: ThreatPayload-only rail → would_enforce dry JSON.

        Disabled unless GHOST_WRAITH_ENABLED=1 (default OFF → 404). Never changes
        the edge and never auto-patches. Keep using Tank; no Dual-LLM bunker here.
        Stronger-than-stock: rails.ensure_threat_payload_before_enforce burns
        anything that is not ThreatPayload before Enforce sees it.
        """
        if not wraith_room.enabled():
            raise HTTPException(404, "Not found.")
        raw = await bounded_json(request, 8_000)
        try:
            guard_inbound_if_enabled(raw)
            payload = airgap_rails.ensure_threat_payload_before_enforce(raw)
        except GuardBurned:
            raise HTTPException(422, GUARD_BURN_DETAIL) from None
        except ThreatBurned:
            raise HTTPException(422, BURN_DETAIL) from None
        return wraith_room.would_enforce(payload)

    @app.get("/ghost/enforce/oss", dependencies=[Depends(require_tank)])
    async def enforce_oss_status():
        """Autumbra Enforce OSS adapter status (Ansible + Terraform stubs). Always readable.

        Does not enable weapons. Live edge changes still require founder Shield tap.
        """
        return enforce_oss_room.status()

    @app.post("/ghost/shields/propose", dependencies=[Depends(require_tank)])
    async def shields_propose(request: Request):
        try:
            body = shield_room.ShieldRequest.model_validate_json(await bounded_json(request, 10_000))
        except ValueError:
            raise HTTPException(422, "Invalid Autumbra Watch request.") from None
        async with app.state.advisory_lock:
            try:
                return shield_room.public_view(await app.state.shields.propose(body))
            except ValueError:
                raise HTTPException(422, "Autumbra Watch only shields our own sites.") from None

    @app.post("/ghost/shields/{shield_id}/raise", dependencies=[Depends(require_tank)])
    async def shields_raise(shield_id: UUID):
        async with app.state.advisory_lock:
            try:
                return shield_room.public_view(await app.state.shields.raise_shield(str(shield_id)))
            except LookupError:
                raise HTTPException(404, "not found") from None

    @app.post("/ghost/shields/{shield_id}/undo", dependencies=[Depends(require_tank)])
    async def shields_undo(shield_id: UUID):
        async with app.state.advisory_lock:
            try:
                return shield_room.public_view(await app.state.shields.undo(str(shield_id)))
            except LookupError:
                raise HTTPException(404, "not found") from None


    # ---------- Autumbra Watch OSS intake (Vector / Fluent Bit / Steampipe / OpenCTI) ----------

    @app.get("/ghost/watch/oss", dependencies=[Depends(require_tank)])
    async def watch_oss_status():
        """Adapter status. Autumbra Watch copy; does not start upstream daemons."""
        return watch_oss_room.status()

    @app.post("/ghost/watch/intake", dependencies=[Depends(require_tank)])
    async def watch_oss_intake(request: Request):
        """Anomaly-only intake → match → ThreatPayload → Shields.propose.

        Flag OFF by default. Raw log bodies rejected by AnomalyEvent (extra=forbid).
        Signals that map to a shield kind (waf/multipart/…) open a synthetic match
        and propose for the founder panel (practice mode when no CF token). Other
        anomalies acknowledge as open_match only. Never raises a shield / Enforce.
        Air Gap #286 guard stays optional and OFF — ThreatPayload burn unchanged.
        """
        if not watch_oss_room.enabled():
            raise HTTPException(404, "Not found.")
        raw = await bounded_json(request, 8_000)
        try:
            # #286 Dual-LLM guard: no-op unless GHOST_GUARDRAILS_ENABLED / AUTUMBRA_GUARDRAILS_ENABLED.
            guard_inbound_if_enabled(raw)
            data = json.loads(raw)
            events = data if isinstance(data, list) else [data]
            accepted = []
            async with app.state.advisory_lock:
                for item in events[:50]:
                    try:
                        event = AnomalyEvent.model_validate(item)
                        # Prefer propose path when signal maps to a shield kind.
                        try:
                            result = await propose_from_anomaly(
                                app.state.shields, app.state.store, PLATFORM_TENANT, event
                            )
                            accepted.append({
                                "action": result["action"],
                                "site": result["site"],
                                "severity": result["severity"],
                                "match_id": result["match_id"],
                                "kind": result["kind"],
                                "shield": shield_room.public_view(result["shield"]),
                                "note": result["note"],
                            })
                            continue
                        except ThreatBurned:
                            payload = handoff_threat(event)
                    except (ThreatBurned, ValueError, TypeError):
                        continue
                    accepted.append({
                        "action": payload.action.value,
                        "site": payload.site,
                        "severity": payload.severity.value,
                        "match_id": payload.match_id,
                    })
            return {
                "accepted": len(accepted),
                "events": accepted,
                "product": "Autumbra Watch",
                "note": (
                    "Anomalies may propose shields for the founder panel. "
                    "Practice mode changes nothing. Founder Shield tap required to raise. "
                    "No Enforce path from this intake."
                ),
            }
        except GuardBurned:
            raise HTTPException(422, GUARD_BURN_DETAIL) from None
        except (ThreatBurned, json.JSONDecodeError, TypeError, ValueError):
            raise HTTPException(422, BURN_DETAIL) from None

    @app.get("/ghost/summary", dependencies=[Depends(require_tank)])
    async def ghost_summary():
        return {**app.state.shields.summary(), "last_cycle": app.state.store.get_state(PLATFORM_TENANT, "last_cycle")}

    return app


app = create_app()
