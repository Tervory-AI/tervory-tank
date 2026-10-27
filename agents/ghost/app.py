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
from .patch_brief import BURN_DETAIL as PATCH_BURN_DETAIL, PatchBurned, accept_patch_brief, passes_severity_bar
from .patch_connect import connect_match_to_plan, threat_to_patch_brief
from .patch_pr import open_dep_bump_pr
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
from .client_settings import (
    ClientAutumbraSettings,
    active_halves,
    connect_copy,
    list_hands,
    load_settings,
    save_settings,
    set_hand,
)
from .market_lab_intel import (
    accept_ioc_bundle,
    backend_status as intel_backend_status,
    receipt_for_bundle_consume,
    register_advisories_from_ioc_bundle,
)
from .webhooks import WebhookRejected, accept_signed, drop_counts
from .red_team import list_exercises, run_exercise
from .enforce_lifecycle import FixtureComposeBackend, plan_create, plan_destroy, receipt_for
from .owner_email import DEFAULT_FIXTURE_TRANSPORT, send_owner_update
from .owner_email_jobs import (
    build_owner_update_from_receipts,
    default_receipt_url,
    list_clients_with_owner,
    run_weekly_owner_updates,
)
from .probes import Probes
from .store import Store
from .tenant_queue import (
    list_founder_console_receipts,
    mirror_settings,
    queue_path_for_tenant,
    queue_root_base,
)
from .threat_queue import (
    ThreatPayloadQueue,
    queue_root_from_env,
    watch_enqueue_approve,
    watch_enqueue_fixture_attack,
    watch_enqueue_undo,
)
from .never_block import may_block_ip


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


def watch_queue_configured() -> bool:
    return bool(
        (os.environ.get("THREAT_PAYLOAD_QUEUE_ROOT") or "").strip()
        or (os.environ.get("THREAT_PAYLOAD_QUEUE") or "").strip()
    )


def watch_threat_queue(tenant_id: str | None = None) -> ThreatPayloadQueue:
    """Production Watch queue door — per-tenant path when tenant_id is given."""
    if tenant_id:
        return ThreatPayloadQueue(queue_path_for_tenant(tenant_id))
    # Legacy single-queue env (one client dogfood).
    return ThreatPayloadQueue(queue_root_from_env())



def _require_tenant_uuid(tenant_id: str | None) -> str:
    """Non-UUID tenant_id → ValueError (mapped to clean 4xx by callers)."""
    tid = (tenant_id or "").strip()
    try:
        return str(UUID(tid))
    except (TypeError, ValueError):
        raise ValueError("tenant_id must be a UUID") from None


def _receipts_for_tenant(tenant_id: str) -> list[dict]:
    """Load Enforce/Watch receipts for one client from their queue box."""
    try:
        q = watch_threat_queue(tenant_id)
    except Exception:
        return []
    try:
        return list(q.list_receipts())
    except Exception:
        return []


def enqueue_fixture_attack_for_watch(
    *,
    raw_log: str,
    site: str,
    address: str,
    reason: str = "fixture attacking address",
    tenant_id: str | None = None,
    advisory: dict | None = None,
    queue: ThreatPayloadQueue | None = None,
) -> dict:
    """Production Watch enqueue entrypoint used by /ghost/autumbra/queue/fixture-attack.

    Validates via never-block rules, then puts a ThreatPayload on that client's queue.
    Does not call Enforce. Never keeps the raw log on the queue.
    """
    if queue is not None:
        q = queue
    elif tenant_id:
        q = watch_threat_queue(tenant_id)
    else:
        q = watch_threat_queue()
    return watch_enqueue_fixture_attack(
        queue=q,
        raw_log=raw_log,
        site=site,
        address=address,
        reason=reason,
        tenant_id=tenant_id,
        advisory=advisory,
    )


async def _weekly_owner_email_loop(app: "FastAPI") -> None:
    """Real scheduled weekly job — every tenant with a stored owner, counts from receipts."""
    # Default 7 days; tests may set AUTUMBRA_WEEKLY_INTERVAL_SEC.
    interval = float(os.environ.get("AUTUMBRA_WEEKLY_INTERVAL_SEC") or str(7 * 24 * 3600))
    if interval < 1:
        interval = 1
    while True:
        # Chunked sleep so lifespan cancel is prompt.
        left = interval
        while left > 0:
            step = 1.0 if left > 1 else left
            await asyncio.sleep(step)
            left -= step
        try:
            store = app.state.store
            clients = list_clients_with_owner(store)
            if not clients:
                continue
            receipts_by_tenant = {
                c.tenant_id: _receipts_for_tenant(c.tenant_id) for c in clients
            }
            run_weekly_owner_updates(
                clients,
                receipts_by_tenant=receipts_by_tenant,
                transport=DEFAULT_FIXTURE_TRANSPORT,
            )
        except Exception:
            pass


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
            app.state.threat_queue = None
            if watch_queue_configured():
                # Prefer root; per-tenant queues opened on demand.
                try:
                    app.state.threat_queue = watch_threat_queue()
                except Exception:
                    app.state.threat_queue = None
            app.state.threat_queue_root = queue_root_base()
            tasks = [
                asyncio.create_task(watch(app)),
                asyncio.create_task(nightly(app)),
                asyncio.create_task(advisory_watch.watch(app)),
                asyncio.create_task(_weekly_owner_email_loop(app)),
            ]
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

    # ---------- GHOST-2 D3: Shields Up (Watch dry-run only; live apply is Enforce) ----------

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
            out = {"accepted": True, "action": payload.action.value,
                   "shield": shield_room.public_view(shield),
                   "note": "Proposed only. Founder must tap Shield before anything changes."}
            # Optional dry Enforce OSS plans (flags OFF by default). Never raise/apply.
            if enforce_oss_room.enabled():
                try:
                    out["enforce_oss"] = enforce_oss_room.receive_from_airgap(payload)
                except ThreatBurned:
                    pass
            return out
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

    @app.post("/ghost/enforce/oss/plan", dependencies=[Depends(require_tank)])
    async def enforce_oss_plan(request: Request):
        """Watch air-gap → Autumbra Enforce OSS dry plans (Ansible + Terraform).

        Disabled unless ENFORCE_OSS_ENABLED=1 (default OFF → 404). Never applies
        playbooks/modules, never calls HF, never changes the edge. Founder Shield
        tap remains the live path.
        """
        if not enforce_oss_room.enabled():
            raise HTTPException(404, "Not found.")
        raw = await bounded_json(request, 8_000)
        try:
            return enforce_oss_room.receive_from_airgap(raw)
        except ThreatBurned:
            raise HTTPException(422, BURN_DETAIL) from None

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

    @app.post("/ghost/patch/accept", dependencies=[Depends(require_tank)])
    async def patch_accept(request: Request):
        """Autumbra patch-as-PR: validate ghost.patch.v1 brief, open draft dep-bump PR or dry-run.

        Flag GHOST_PATCH_PR_ENABLED/PATCH_PR_ENABLED OFF by default. Never merges. Never deploys.
        """
        raw = await bounded_json(request, 10_000)
        try:
            brief = accept_patch_brief(raw)
        except PatchBurned:
            raise HTTPException(422, PATCH_BURN_DETAIL) from None
        if not passes_severity_bar(brief):
            raise HTTPException(422, PATCH_BURN_DETAIL)
        result = open_dep_bump_pr(brief)
        return {
            "accepted": True,
            "action": brief.action,
            "schema_version": brief.schema_version,
            **result,
        }

    @app.post("/ghost/patch/from-match", dependencies=[Depends(require_tank)])
    async def patch_from_match(request: Request):
        """CONNECT: advisory match fixture → PatchBrief → draft/dry-run plan. Never merges."""
        raw = await bounded_json(request, 20_000)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
            raise HTTPException(422, PATCH_BURN_DETAIL) from None
        if not isinstance(data, dict):
            raise HTTPException(422, PATCH_BURN_DETAIL)
        try:
            return connect_match_to_plan(data)
        except PatchBurned:
            raise HTTPException(422, PATCH_BURN_DETAIL) from None

    @app.post("/ghost/patch/from-threat", dependencies=[Depends(require_tank)])
    async def patch_from_threat(request: Request):
        """CONNECT: ThreatPayload-shaped facts → PatchBrief → draft/dry-run. Never merges."""
        raw = await bounded_json(request, 12_000)
        try:
            brief = threat_to_patch_brief(raw)
        except PatchBurned:
            raise HTTPException(422, PATCH_BURN_DETAIL) from None
        if not passes_severity_bar(brief):
            raise HTTPException(422, PATCH_BURN_DETAIL)
        result = open_dep_bump_pr(brief)
        return {
            "connected": True,
            "action": brief.action,
            "schema_version": brief.schema_version,
            "brief": brief.model_dump(mode="json"),
            **result,
        }


    # ---------- Autumbra product surfaces (settings, intel consume, webhooks, lifecycle) ----------

    @app.get("/ghost/autumbra/settings", dependencies=[Depends(require_tank)])
    async def autumbra_settings_get(tenant_id: str = Query(default=PLATFORM_TENANT)):
        settings = load_settings(app.state.store, tenant_id)
        halves = active_halves(settings)
        return {
            "settings": settings.model_dump(),
            "halves": halves,
            "hands": list_hands(settings),
            "copy": connect_copy(settings),
        }

    @app.post("/ghost/autumbra/settings", dependencies=[Depends(require_tank)])
    async def autumbra_settings_set(request: Request):
        raw = await bounded_json(request, 8_000)
        try:
            data = json.loads(raw.decode("utf-8"))
            settings = ClientAutumbraSettings.model_validate(data)
        except Exception:
            raise HTTPException(422, "Settings were not understood.") from None
        saved = save_settings(app.state.store, settings)
        # Mirror into that client's queue box so Enforce reloads and obeys the mode.
        mirrored = False
        try:
            qpath = queue_path_for_tenant(saved.tenant_id)
            mirror_settings(saved, qpath)
            mirrored = True
        except Exception:
            # Single-queue dogfood: mirror into THREAT_PAYLOAD_QUEUE if configured.
            try:
                if watch_queue_configured():
                    mirror_settings(saved, queue_root_from_env())
                    mirrored = True
            except Exception:
                mirrored = False
        receipt = {
            "product": "Autumbra",
            "kind": "settings_change",
            "tenant_id": saved.tenant_id,
            "shield_mode": saved.shield_mode.value,
            "fix_mode": saved.fix_mode.value,
            "mirrored_to_enforce_box": mirrored,
            "undo": {"restore_defaults": True},
        }
        return {
            "settings": saved.model_dump(),
            "halves": active_halves(saved),
            "hands": list_hands(saved),
            "copy": connect_copy(saved),
            "receipt": receipt,
        }

    @app.get("/ghost/autumbra/hands", dependencies=[Depends(require_tank)])
    async def autumbra_hands_get(tenant_id: str = Query(default=PLATFORM_TENANT)):
        """Agnostic optional connects. No assumed provider. No Pro."""
        settings = load_settings(app.state.store, tenant_id)
        return {
            "hands": list_hands(settings),
            "halves": active_halves(settings),
            "copy": connect_copy(settings),
            "note": "Optional hands only. Stack/advisories/receipts work with zero connects.",
        }

    @app.post("/ghost/autumbra/hands", dependencies=[Depends(require_tank)])
    async def autumbra_hands_set(request: Request):
        """Connect or disconnect one optional hand. Client modes stay the only clamp."""
        raw = await bounded_json(request, 4_000)
        try:
            data = json.loads(raw.decode("utf-8"))
            tenant_id = str(data.get("tenant_id") or PLATFORM_TENANT)
            hand = str(data["hand"])
            connected = bool(data["connected"])
        except Exception:
            raise HTTPException(422, "Hand change was not understood.") from None
        settings = load_settings(app.state.store, tenant_id)
        try:
            updated = set_hand(settings, hand, connected=connected)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        saved = save_settings(app.state.store, updated)
        return {
            "settings": saved.model_dump(),
            "hands": list_hands(saved),
            "halves": active_halves(saved),
            "copy": connect_copy(saved),
        }

    @app.get("/ghost/autumbra/sources", dependencies=[Depends(require_tank)])
    async def autumbra_sources(tenant_id: str = Query(default=PLATFORM_TENANT)):
        # Clients never see a feed list. Intel backend is Market Lab.
        _ = tenant_id
        return {"sources": [], "client_visible_feed_list": False, **intel_backend_status()}

    @app.post("/ghost/autumbra/intel/consume", dependencies=[Depends(require_tank)])
    async def autumbra_intel_consume(request: Request):
        """Consume a Market Lab IOC bundle. Name sources on the receipt. No Autumbra registry."""
        raw = await bounded_json(request, 64_000)
        try:
            data = json.loads(raw.decode("utf-8"))
            tenant_id = str(data.get("tenant_id") or PLATFORM_TENANT)
            bundle_raw = data.get("bundle") if isinstance(data.get("bundle"), dict) else data
        except Exception:
            raise HTTPException(422, "Intel bundle was not understood.") from None
        try:
            bundle = accept_ioc_bundle(bundle_raw)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        register_advisories_from_ioc_bundle(bundle)
        receipt = receipt_for_bundle_consume(bundle, tenant_id=tenant_id)
        return {
            "accepted": True,
            "bundle_id": bundle["bundle_id"],
            "indicator_count": len(bundle.get("indicators") or []),
            "receipt": receipt,
            "client_visible_feed_list": False,
        }

    @app.post("/ghost/autumbra/webhooks/{provider}")
    async def autumbra_webhook(provider: str, request: Request):
        """Signature check FIRST — before any Tank auth that would 404.

        Correctly signed webhook → never-block check → ThreatPayload → client's queue.
        Replay refused (timestamp window + nonce). Body is never stored.
        """
        raw = await request.body()
        if len(raw) > 64_000:
            raise HTTPException(413, "Too large.")
        signature = request.headers.get("x-autumbra-signature") or request.headers.get(
            "cf-webhook-signature"
        )
        timestamp = request.headers.get("x-autumbra-timestamp")
        nonce = request.headers.get("x-autumbra-nonce")
        try:
            envelope = accept_signed(
                provider, raw, signature=signature, timestamp=timestamp, nonce=nonce
            )
        except WebhookRejected:
            return JSONResponse(
                {"accepted": False, "stored": False, "drops": drop_counts()},
                status_code=401,
            )
        # Parse working-memory JSON only after signature OK. Never persist raw body.
        queued = False
        queue_receipt = None
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            data = {}
        if isinstance(data, dict):
            address = str(data.get("address") or data.get("ip") or "").strip()
            site = str(data.get("site") or data.get("host") or "").strip()
            tenant_id = str(data.get("tenant_id") or "").strip()
            raw_log = str(data.get("raw_log") or data.get("message") or f"webhook {provider}")
            if address and site and tenant_id and watch_queue_configured():
                try:
                    tenant_id = _require_tenant_uuid(tenant_id)
                except ValueError:
                    return JSONResponse(
                        {"accepted": False, "stored": False, "detail": "tenant_id must be a UUID"},
                        status_code=400,
                    )
                ok, why = may_block_ip(address, raw_log=raw_log)
                if ok:
                    advisory = data.get("advisory") if isinstance(data.get("advisory"), dict) else None
                    try:
                        queue_receipt = enqueue_fixture_attack_for_watch(
                            raw_log=raw_log,
                            site=site,
                            address=address,
                            reason=str(data.get("reason") or f"signed {provider} webhook")[:300],
                            tenant_id=tenant_id,
                            advisory=advisory,
                        )
                    except ValueError as exc:
                        return JSONResponse(
                            {"accepted": False, "stored": False, "detail": str(exc)},
                            status_code=400,
                        )
                    queued = bool(queue_receipt.get("queued"))
                else:
                    queue_receipt = {"queued": False, "note": why, "outcome": "refused_never_block"}
        return {
            "accepted": True,
            "stored": False,
            "provider": envelope["provider"],
            "bytes": envelope["bytes"],
            "queued": queued,
            "queue_receipt": queue_receipt,
            "action": "enqueue_threat_payload" if queued else "accepted_no_action",
        }

    @app.get("/ghost/autumbra/exercises", dependencies=[Depends(require_tank)])
    async def autumbra_exercises():
        return {"exercises": list_exercises(), "note": "Tervory's own sites only; client needs written permission."}

    @app.post("/ghost/autumbra/exercises/run", dependencies=[Depends(require_tank)])
    async def autumbra_exercise_run(request: Request):
        raw = await bounded_json(request, 8_000)
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            raise HTTPException(422, "Exercise was not understood.") from None
        tenant_id = str(data.get("tenant_id") or PLATFORM_TENANT)
        settings = load_settings(app.state.store, tenant_id)
        try:
            receipt = run_exercise(
                str(data.get("exercise_id") or ""),
                target_site=str(data.get("target_site") or ""),
                settings=settings,
                fixture_log=str(data.get("fixture_log") or ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return receipt


    @app.post("/ghost/autumbra/queue/fixture-attack", dependencies=[Depends(require_tank)])
    async def autumbra_queue_fixture_attack(request: Request):
        """Watch product door: dirty log → ThreatPayload → that client's queue.

        Does not call Enforce. Burned/unknown-site input → clean 4xx + burn receipt.
        """
        if not watch_queue_configured() and getattr(app.state, "threat_queue", None) is None:
            raise HTTPException(503, "THREAT_PAYLOAD_QUEUE is not configured.")
        raw = await bounded_json(request, 32_000)
        try:
            data = json.loads(raw.decode("utf-8"))
            raw_log = str(data["raw_log"])
            site = str(data["site"])
            address = str(data["address"])
            reason = str(data.get("reason") or "fixture attacking address")
            tenant_id = str(data.get("tenant_id") or "").strip() or None
            advisory = data.get("advisory") if isinstance(data.get("advisory"), dict) else None
        except Exception:
            raise HTTPException(422, "Fixture attack was not understood.") from None
        if tenant_id:
            try:
                tenant_id = _require_tenant_uuid(tenant_id)
            except ValueError:
                raise HTTPException(400, "tenant_id must be a UUID") from None
            try:
                queue = watch_threat_queue(tenant_id)
            except ValueError:
                raise HTTPException(400, "tenant_id must be a UUID") from None
            except Exception as exc:
                raise HTTPException(422, str(exc)) from None
        else:
            queue = getattr(app.state, "threat_queue", None)
        try:
            receipt = enqueue_fixture_attack_for_watch(
                raw_log=raw_log,
                site=site,
                address=address,
                reason=reason,
                tenant_id=tenant_id,
                advisory=advisory,
                queue=queue,
            )
        except ThreatBurned:
            burn_receipt = {
                "product": "Autumbra",
                "role": "Watch",
                "kind": "burn",
                "outcome": "burned",
                "queued": False,
                "detail": BURN_DETAIL,
                "tenant_id": tenant_id,
            }
            return JSONResponse(burn_receipt, status_code=400)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        return receipt

    @app.post("/ghost/autumbra/queue/undo", dependencies=[Depends(require_tank)])
    async def autumbra_queue_undo(request: Request):
        """Client undo: validated ThreatPayload (undo_shield) into that client's queue."""
        if not watch_queue_configured():
            raise HTTPException(503, "THREAT_PAYLOAD_QUEUE is not configured.")
        raw = await bounded_json(request, 8_000)
        try:
            data = json.loads(raw.decode("utf-8"))
            tenant_id = str(data["tenant_id"])
            site = str(data["site"])
            rule_id = data.get("rule_id")
            prior_receipt_id = data.get("prior_receipt_id")
        except Exception:
            raise HTTPException(422, "Undo was not understood.") from None
        try:
            tenant_id = _require_tenant_uuid(tenant_id)
            q = watch_threat_queue(tenant_id)
            return watch_enqueue_undo(
                queue=q,
                rule_id=str(rule_id) if rule_id else None,
                prior_receipt_id=str(prior_receipt_id) if prior_receipt_id else None,
                site=site,
                tenant_id=tenant_id,
            )
        except ThreatBurned:
            return JSONResponse(
                {"outcome": "burned", "detail": BURN_DETAIL, "queued": False},
                status_code=400,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        except Exception as exc:
            raise HTTPException(422, str(exc)) from None

    @app.post("/ghost/autumbra/queue/approve", dependencies=[Depends(require_tank)])
    async def autumbra_queue_approve(request: Request):
        """Approve a pending shield via ThreatPayload into that client's queue."""
        if not watch_queue_configured():
            raise HTTPException(503, "THREAT_PAYLOAD_QUEUE is not configured.")
        raw = await bounded_json(request, 8_000)
        try:
            data = json.loads(raw.decode("utf-8"))
            tenant_id = str(data["tenant_id"])
            site = str(data["site"])
            prior_receipt_id = str(data["prior_receipt_id"])
        except Exception:
            raise HTTPException(422, "Approve was not understood.") from None
        try:
            tenant_id = _require_tenant_uuid(tenant_id)
            q = watch_threat_queue(tenant_id)
            return watch_enqueue_approve(
                queue=q,
                prior_receipt_id=prior_receipt_id,
                site=site,
                tenant_id=tenant_id,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        except ThreatBurned:
            return JSONResponse(
                {"outcome": "burned", "detail": BURN_DETAIL, "queued": False},
                status_code=400,
            )

    @app.get("/ghost/autumbra/receipts", dependencies=[Depends(require_tank)])
    async def autumbra_receipts(tenant_id: str = Query(...)):
        """Founder console path: receipts for one client (timestamps + tenant_id)."""
        try:
            q = watch_threat_queue(tenant_id)
        except Exception as exc:
            raise HTTPException(404, str(exc)) from None
        disk = q.list_receipts()
        console = list_founder_console_receipts(q.root)
        # Prefer console view; fall back to disk receipts.
        by_id = {str(r.get("id")): r for r in disk if r.get("id")}
        for r in console:
            by_id[str(r.get("id"))] = r
        return {
            "tenant_id": tenant_id,
            "receipts": list(by_id.values()),
            "count": len(by_id),
            "founder_console": True,
        }

    @app.get("/ghost/autumbra/receipts/weekly/{tenant_id}")
    async def autumbra_weekly_receipt_page(tenant_id: str):
        """Page target for weekly email links — lists that week's receipts, each linked."""
        from .owner_email_jobs import PROTECT_HOST, week_bounds, _parse_receipt_time

        try:
            tid = _require_tenant_uuid(tenant_id)
        except ValueError:
            raise HTTPException(400, "tenant_id must be a UUID") from None
        week_start, week_end = week_bounds()
        rows = []
        for receipt in _receipts_for_tenant(tid):
            moment = _parse_receipt_time(receipt)
            if moment is None or moment < week_start or moment > week_end:
                continue
            rid = str(receipt.get("id") or "")
            rows.append({
                "id": rid,
                "timestamp": receipt.get("timestamp") or receipt.get("at"),
                "outcome": receipt.get("outcome"),
                "severity": receipt.get("severity"),
                "advisory_url": receipt.get("advisory_url"),
                "site": receipt.get("site"),
                "url": f"{PROTECT_HOST}/autumbra/undo/{rid}" if rid else "",
                "receipt": receipt,
            })
        return {
            "product": "Autumbra",
            "kind": "weekly_receipts",
            "tenant_id": tid,
            "page": "exists",
            "week_start": week_start.isoformat().replace("+00:00", "Z"),
            "week_end": week_end.isoformat().replace("+00:00", "Z"),
            "receipts": rows,
            "count": len(rows),
            "note": "Weekly owner-update receipt page.",
        }

    @app.post("/ghost/autumbra/enforce/plan-create", dependencies=[Depends(require_tank)])
    async def autumbra_enforce_plan_create(request: Request):
        raw = await bounded_json(request, 4_000)
        try:
            data = json.loads(raw.decode("utf-8"))
            tenant_id = str(data["tenant_id"])
            existing = int(data.get("existing_count") or 0)
            execute = bool(data.get("execute"))
        except Exception:
            raise HTTPException(422, "Create plan was not understood.") from None
        try:
            plan = plan_create(tenant_id, existing_count=existing)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(422, str(exc)) from None
        if execute:
            root = os.environ.get("AUTUMBRA_FIXTURE_COMPOSE_ROOT", "").strip()
            if not root:
                raise HTTPException(422, "Fixture compose root is not configured.")
            receipt = FixtureComposeBackend(Path(root)).create(plan)
        else:
            receipt = receipt_for(plan)
        return {"plan": plan, "receipt": receipt}

    @app.post("/ghost/autumbra/enforce/plan-destroy", dependencies=[Depends(require_tank)])
    async def autumbra_enforce_plan_destroy(request: Request):
        raw = await bounded_json(request, 4_000)
        try:
            data = json.loads(raw.decode("utf-8"))
            plan = plan_destroy(str(data["tenant_id"]))
            execute = bool(data.get("execute"))
        except Exception:
            raise HTTPException(422, "Destroy plan was not understood.") from None
        if execute:
            root = os.environ.get("AUTUMBRA_FIXTURE_COMPOSE_ROOT", "").strip()
            if not root:
                raise HTTPException(422, "Fixture compose root is not configured.")
            receipt = FixtureComposeBackend(Path(root)).destroy(plan)
        else:
            receipt = receipt_for(plan)
        return {"plan": plan, "receipt": receipt}

    @app.post("/ghost/autumbra/owner-update", dependencies=[Depends(require_tank)])
    async def autumbra_owner_update(request: Request):
        """Build the owner email from receipts in code and call the sender. No model.

        Recipient is ONLY the owner_email stored in the client's settings.
        A request body can never name or override the recipient.
        Every count is built from receipts — never from the request body.
        """
        raw = await bounded_json(request, 20_000)
        try:
            data = json.loads(raw.decode("utf-8"))
            tenant_id = str(
                data.get("tenant_id")
                or (data.get("settings") or {}).get("tenant_id")
                or ""
            ).strip()
            if not tenant_id:
                raise ValueError("tenant_id required")
            tenant_id = _require_tenant_uuid(tenant_id)
            # Stored settings only — ignore any owner_email in the request body.
            settings = load_settings(app.state.store, tenant_id)
            to = str(settings.owner_email or "").strip()
            if not to:
                raise ValueError("recipient must come from the client's settings")
            if "owner_email" in (data.get("settings") or {}):
                requested = str((data.get("settings") or {}).get("owner_email") or "").strip()
                if requested and requested != to:
                    raise ValueError("request cannot name the recipient")
            # Counts from receipts only. Request body numbers are ignored.
            receipts = _receipts_for_tenant(tenant_id)
            email = build_owner_update_from_receipts(
                settings=settings,
                receipts=receipts,
                receipt_url=default_receipt_url(tenant_id),
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except Exception:
            raise HTTPException(422, "Owner update was not understood.") from None
        sent = send_owner_update(email, to=to, transport=DEFAULT_FIXTURE_TRANSPORT)
        return {**email, **sent}

    @app.get("/ghost/autumbra/jobs", dependencies=[Depends(require_tank)])
    async def autumbra_jobs():
        """Scheduled Autumbra jobs (weekly owner update is a real entry)."""
        from .owner_email_jobs import list_jobs
        return {"jobs": list_jobs()}

    @app.get("/ghost/summary", dependencies=[Depends(require_tank)])
    async def ghost_summary():
        return {**app.state.shields.summary(), "last_cycle": app.state.store.get_state(PLATFORM_TENANT, "last_cycle")}

    return app


app = create_app()
