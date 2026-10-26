"""Separately runnable Autumbra Enforce process.

Own entrypoint — not ghost.app. Starts without a Tank key. Does not parse raw
logs: HTTP apply/undo never read request bodies; in-process callers hand a
ThreatPayload (or the prior apply receipt for undo). Fixture edge control makes
apply/undo real for dogfood. Client shield mode is loaded for TENANT_ID.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .client_settings import ClientAutumbraSettings, load_settings
from .enforce_apply import apply_from_payload, undo_applied
from .fixture_edge import DEFAULT_CONTROL
from .store import Store
from .threat_payload import ThreatPayload


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
                "or the prior apply receipt via submit_undo()."
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


def create_enforce_app() -> FastAPI:
    app = FastAPI(title="Autumbra Enforce", docs_url=None, redoc_url=None)
    app.state.control = DEFAULT_CONTROL
    app.state.settings = load_enforce_client_settings()

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
