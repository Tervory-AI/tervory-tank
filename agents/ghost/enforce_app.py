"""Separately runnable Autumbra Enforce process.

Own entrypoint — not ghost.app. Starts without a Tank key. Does not parse raw
logs: HTTP apply/undo never read request bodies; in-process callers hand a
ThreatPayload (or the prior apply receipt for undo). The production product
path drains ThreatPayloads from THREAT_PAYLOAD_QUEUE (background loop +
drain_once_for_enforce). Fixture edge control makes apply/undo real for
dogfood. Client shield mode is loaded for TENANT_ID.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .client_settings import ClientAutumbraSettings, load_settings
from .enforce_apply import apply_from_payload, undo_applied
from .fixture_edge import DEFAULT_CONTROL
from .never_block import ActionCap
from .store import Store
from .threat_payload import ThreatPayload
from .threat_queue import ThreatPayloadQueue, enforce_drain_once, queue_root_from_env


def _content_length(request: Request) -> int:
    raw = request.headers.get("content-length")
    if raw is None or raw == "":
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return -1  # malformed — treat as present/raw


def _refuse_raw_http() -> JSONResponse:
    return JSONResponse(
        {
            "accepted": False,
            "raw_log_seen": True,
            "detail": (
                "Enforce does not parse request bodies. "
                "Hand a ThreatPayload object via submit_payload(), "
                "or the prior apply receipt via submit_undo(). "
                "Production path drains THREAT_PAYLOAD_QUEUE via "
                "drain_once_for_enforce()."
            ),
        },
        status_code=415,
    )


def load_enforce_client_settings() -> ClientAutumbraSettings:
    """Load this Enforce room's client modes for TENANT_ID from DATA_DIR store.

    Default shield/fix mode is approve-each (ClientAutumbraSettings). Tervory
    never changes a client's stored choice.
    """
    tenant_id = (os.environ.get("TENANT_ID") or "").strip() or (
        "00000000-0000-0000-0000-0000000000ef"
    )
    site_name = (os.environ.get("SITE_NAME") or "").strip() or "coolify.tervory.com"
    data_dir = Path(os.environ.get("DATA_DIR") or "/data")
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        store = Store(data_dir / "autumbra_enforce.sqlite3")
        settings = load_settings(store, tenant_id)
    except Exception:
        settings = ClientAutumbraSettings(tenant_id=tenant_id, site_name=site_name)
    if not settings.site_name and site_name:
        settings = ClientAutumbraSettings.model_validate(
            {**settings.model_dump(), "site_name": site_name}
        )
    return settings


def queue_configured() -> bool:
    return bool((os.environ.get("THREAT_PAYLOAD_QUEUE") or "").strip())


def enforce_threat_queue() -> ThreatPayloadQueue:
    """Production Enforce queue door — path from THREAT_PAYLOAD_QUEUE."""
    return ThreatPayloadQueue(queue_root_from_env())


def drain_once_for_enforce(
    *,
    app: FastAPI | None = None,
    queue: ThreatPayloadQueue | None = None,
    settings: ClientAutumbraSettings | None = None,
    control=None,
    action_cap: ActionCap | None = None,
    source_credits: list[dict[str, str]] | None = None,
) -> dict[str, Any] | None:
    """Production Enforce drain entrypoint used by the process drain loop.

    Reads one ThreatPayload from the queue door, then shield → health →
    auto-undo on fail → receipt. Never parses raw/str bodies.
    """
    target = app
    if target is None:
        # Lazy: prefer the module-level app when the drain loop is running.
        target = globals().get("app")
    q = queue
    if q is None:
        if target is not None and getattr(target.state, "threat_queue", None) is not None:
            q = target.state.threat_queue
        else:
            q = enforce_threat_queue()
    cfg = settings
    if cfg is None and target is not None:
        cfg = getattr(target.state, "settings", None)
    if cfg is None:
        cfg = load_enforce_client_settings()
    edge = control
    if edge is None and target is not None:
        edge = getattr(target.state, "control", None)
    if edge is None:
        edge = DEFAULT_CONTROL
    cap = action_cap
    if cap is None and target is not None:
        cap = getattr(target.state, "action_cap", None)
    if cap is None:
        cap = ActionCap()
    return enforce_drain_once(
        q,
        settings=cfg,
        control=edge,
        action_cap=cap,
        source_credits=source_credits,
    )


async def _queue_drain_loop(app: FastAPI) -> None:
    """Background loop: drain ThreatPayload queue while the process is up."""
    interval = float(os.environ.get("ENFORCE_DRAIN_INTERVAL_SEC") or "1.0")
    if interval < 0.05:
        interval = 0.05
    while True:
        # Sleep first so an explicit /v1/drain-once (or startup attach) is not raced.
        await asyncio.sleep(interval)
        try:
            if getattr(app.state, "threat_queue", None) is not None:
                drain_once_for_enforce(app=app)
        except Exception:
            # Keep the process alive; next tick retries. No raw body parse.
            pass


def create_enforce_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.control = DEFAULT_CONTROL
        app.state.settings = load_enforce_client_settings()
        app.state.action_cap = ActionCap()
        app.state.threat_queue = None
        app.state.drain_loop_running = False
        drain_task: asyncio.Task | None = None
        if queue_configured():
            app.state.threat_queue = enforce_threat_queue()
            drain_task = asyncio.create_task(_queue_drain_loop(app))
            app.state.drain_loop_running = True
        try:
            yield
        finally:
            app.state.drain_loop_running = False
            if drain_task is not None:
                drain_task.cancel()
                await asyncio.gather(drain_task, return_exceptions=True)

    app = FastAPI(title="Autumbra Enforce", docs_url=None, redoc_url=None, lifespan=lifespan)
    # Defaults for callers that construct routes without entering lifespan
    # (unit helpers). Lifespan overwrites these when the process runs.
    app.state.control = DEFAULT_CONTROL
    app.state.settings = load_enforce_client_settings()
    app.state.action_cap = ActionCap()
    app.state.threat_queue = None
    app.state.drain_loop_running = False

    @app.get("/health")
    async def health() -> dict[str, Any]:
        # No TANK_KEY. Enforce never calls a model.
        return {
            "ok": True,
            "role": "enforce",
            "tank_key_configured": bool(os.environ.get("TANK_KEY", "").strip()),
            "control": "fixture_edge",
            "blocked": len(app.state.control.list_blocked()),
            "shield_mode": app.state.settings.shield_mode.value,
            "tenant_id": app.state.settings.tenant_id,
            "threat_payload_queue_configured": queue_configured(),
            "drain_loop_running": bool(getattr(app.state, "drain_loop_running", False)),
            "drain_entrypoint": "ghost.enforce_app:drain_once_for_enforce",
        }

    @app.post("/v1/apply")
    async def apply_http(request: Request) -> JSONResponse:
        """Refuse raw bodies — never read or parse bytes inside Enforce."""
        # Do not await request.body() / request.json() — air gap.
        if _content_length(request) != 0:
            return _refuse_raw_http()
        raise HTTPException(415, "Enforce does not parse request bodies.")

    @app.post("/v1/undo")
    async def undo_http(request: Request) -> JSONResponse:
        """Same door as apply: no request.json() of arbitrary bytes."""
        if _content_length(request) != 0:
            return _refuse_raw_http()
        raise HTTPException(415, "Enforce does not parse request bodies.")

    @app.post("/v1/drain-once")
    async def drain_once_http(request: Request) -> JSONResponse:
        """Explicit process drain door. No body parse — queue only."""
        if _content_length(request) != 0:
            return _refuse_raw_http()
        if not queue_configured() and getattr(app.state, "threat_queue", None) is None:
            raise HTTPException(503, "THREAT_PAYLOAD_QUEUE is not configured.")
        receipt = drain_once_for_enforce(app=app)
        if receipt is None:
            return JSONResponse({"drained": False, "receipt": None})
        return JSONResponse({"drained": True, "receipt": receipt})

    return app


def submit_payload(
    payload: ThreatPayload,
    *,
    app: FastAPI | None = None,
    settings: ClientAutumbraSettings | None = None,
    source_credits: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """In-process door: ThreatPayload object only → apply_from_payload."""
    if not isinstance(payload, ThreatPayload):
        raise TypeError("Enforce accepts ThreatPayload only.")
    target = app or create_enforce_app()
    control = getattr(target.state, "control", DEFAULT_CONTROL)
    cfg = settings or getattr(target.state, "settings", None)
    if cfg is None:
        cfg = load_enforce_client_settings()
    return apply_from_payload(
        payload, settings=cfg, control=control, source_credits=source_credits
    )


def submit_undo(
    prior_receipt: dict[str, Any],
    *,
    app: FastAPI | None = None,
) -> dict[str, Any]:
    """In-process undo door: prior apply receipt object only — never raw HTTP."""
    if not isinstance(prior_receipt, dict):
        raise TypeError("submit_undo accepts the prior Enforce receipt dict only.")
    target = app or create_enforce_app()
    control = getattr(target.state, "control", DEFAULT_CONTROL)
    return undo_applied(prior_receipt, control=control)


app = create_enforce_app()


def main() -> None:
    """CLI entry: uvicorn ghost.enforce_app:app — no Tank key required."""
    import uvicorn

    # Prove we do not need TANK_KEY to boot.
    if os.environ.get("AUTUMBRA_ENFORCE_DROP_TANK_KEY") == "1":
        os.environ.pop("TANK_KEY", None)
    host = os.environ.get("ENFORCE_HOST", "127.0.0.1")
    port = int(os.environ.get("ENFORCE_PORT", "8000"))
    uvicorn.run("ghost.enforce_app:app", host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
