"""Separately runnable Autumbra Enforce process.

Own entrypoint — not ghost.app. Starts without a Tank key. Does not parse raw
logs: HTTP apply refuses bodies; in-process callers hand a ThreatPayload to
apply_from_payload. Fixture edge control makes apply/undo real for dogfood.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .client_settings import ApplyMode, ClientAutumbraSettings
from .enforce_apply import apply_from_payload, undo_applied
from .fixture_edge import DEFAULT_CONTROL, reset_default_control
from .threat_payload import ThreatPayload


def create_enforce_app() -> FastAPI:
    app = FastAPI(title="Autumbra Enforce", docs_url=None, redoc_url=None)
    app.state.control = DEFAULT_CONTROL
    app.state.settings = ClientAutumbraSettings(
        tenant_id=os.environ.get("TENANT_ID") or "00000000-0000-0000-0000-0000000000ef",
        shield_mode=ApplyMode.auto_when_checks_pass,
        site_name=os.environ.get("SITE_NAME") or "coolify.tervory.com",
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        # No TANK_KEY. Enforce never calls a model.
        return {
            "ok": True,
            "role": "enforce",
            "tank_key_configured": bool(os.environ.get("TANK_KEY", "").strip()),
            "control": "fixture_edge",
            "blocked": len(app.state.control.list_blocked()),
        }

    @app.post("/v1/apply")
    async def apply_http(request: Request) -> JSONResponse:
        """Refuse raw bodies — Enforce does not parse. Use in-process submit."""
        body = await request.body()
        if body:
            return JSONResponse(
                {
                    "accepted": False,
                    "raw_log_seen": True,
                    "detail": (
                        "Enforce does not parse request bodies. "
                        "Hand a ThreatPayload object via submit_payload()."
                    ),
                },
                status_code=415,
            )
        raise HTTPException(415, "Enforce does not parse request bodies.")

    @app.post("/v1/undo")
    async def undo_http(request: Request) -> dict[str, Any]:
        raw = await request.json()
        receipt = raw.get("receipt") if isinstance(raw, dict) else None
        if not isinstance(receipt, dict):
            raise HTTPException(422, "undo needs the prior Enforce receipt")
        try:
            return undo_applied(receipt, control=app.state.control)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from None

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
        cfg = ClientAutumbraSettings(
            tenant_id="00000000-0000-0000-0000-0000000000ef",
            shield_mode=ApplyMode.auto_when_checks_pass,
        )
    return apply_from_payload(
        payload, settings=cfg, control=control, source_credits=source_credits
    )


app = create_enforce_app()


def main() -> None:
    """CLI entry: uvicorn ghost.enforce_app:app — no Tank key required."""
    import uvicorn

    # Prove we do not need TANK_KEY to boot.
    os.environ.pop("TANK_KEY", None) if os.environ.get("AUTUMBRA_ENFORCE_DROP_TANK_KEY") == "1" else None
    host = os.environ.get("ENFORCE_HOST", "127.0.0.1")
    port = int(os.environ.get("ENFORCE_PORT", "8000"))
    uvicorn.run("ghost.enforce_app:app", host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
