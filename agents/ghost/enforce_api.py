"""Lifecycle API shared by offline fixture routes and the isolated control service."""
import json
import os
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request

from .enforce_lifecycle import (CoolifyEnforceBackend, Refused, coolify_configured,
                                FixtureComposeBackend, plan_create, plan_destroy, receipt_for)


def register(app, require_tank, bounded_json):
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
        if execute and coolify_configured():
            try:
                async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as http:
                    backend = CoolifyEnforceBackend.from_env(http)
                    plan = await backend.create_plan(tenant_id)
                    receipt = await backend.create(plan)
                return {"plan": plan, "receipt": receipt}
            except (ValueError, RuntimeError) as exc:
                raise HTTPException(422, str(exc)) from None
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
        if execute and coolify_configured():
            try:
                async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as http:
                    receipt = await CoolifyEnforceBackend.from_env(http).destroy(plan)
                return {"plan": plan, "receipt": receipt}
            except (ValueError, RuntimeError) as exc:
                raise HTTPException(422, str(exc)) from None
        if execute:
            root = os.environ.get("AUTUMBRA_FIXTURE_COMPOSE_ROOT", "").strip()
            if not root:
                raise HTTPException(422, "Fixture compose root is not configured.")
            receipt = FixtureComposeBackend(Path(root)).destroy(plan)
        else:
            receipt = receipt_for(plan)
        return {"plan": plan, "receipt": receipt}

    @app.get("/ghost/autumbra/enforce/list", dependencies=[Depends(require_tank)])
    async def autumbra_enforce_list():
        if not coolify_configured():
            raise HTTPException(422, "Autumbra Coolify settings are not configured.")
        try:
            async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as http:
                rows = await CoolifyEnforceBackend.from_env(http).list()
                return {"applications": [{key: row[key] for key in ("name", "uuid", "status")} for row in rows]}
        except Refused as exc:
            raise HTTPException(422, str(exc)) from None


def create_app():
    # Reuse the existing HMAC and body bound; no Watch lifespan/background tasks.
    from .app import require_tank, bounded_json
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    register(app, require_tank, bounded_json)
    return app
