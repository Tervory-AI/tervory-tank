"""Verified tenant+user for memory-backed paid work.

Bound only from the current shared Tank user assertion. Body-supplied identity
never overrides the verified actor.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_actor: ContextVar[dict[str, str] | None] = ContextVar("rig_verified_actor", default=None)


def set_verified_actor(*, tenant_id: str, user_id: str) -> Any:
    return _actor.set({"tenant_id": str(tenant_id), "user_id": str(user_id)})


def reset_verified_actor(token: Any) -> None:
    _actor.reset(token)


def get_verified_actor() -> dict[str, str] | None:
    value = _actor.get()
    if not value:
        return None
    tenant = str(value.get("tenant_id") or "").strip()
    user = str(value.get("user_id") or "").strip()
    if not tenant or not user:
        return None
    return {"tenant_id": tenant, "user_id": user}


class VerifiedActorMiddleware:
    """Bind optional shopper identity before handlers or spawned tasks run."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith("/v1/rig/"):
            return await self.app(scope, receive, send)
        import json

        from chassis.user_assertion import HEADER, signed_user
        from starlette.requests import Request
        request = Request(scope, receive)
        token = _actor.set(None)
        try:
            if request.headers.get(HEADER):
                raw = await request.body()
                try:
                    body = json.loads(raw) if raw else {}
                    if not isinstance(body, dict):
                        raise ValueError("Object required")
                    tenant = request.query_params.get("tenant_id") or body.get("tenant_id")
                    actor = await signed_user(request, tenant_id=str(tenant), product="rig")
                except (ValueError, TypeError):
                    actor = None
                if actor:
                    _actor.set({"tenant_id": actor.tenant_id, "user_id": actor.user_id})
                sent = False
                async def replay():
                    nonlocal sent
                    if not sent:
                        sent = True
                        return {"type": "http.request", "body": raw, "more_body": False}
                    return await receive()
                await self.app(scope, replay, send)
            else:
                await self.app(scope, receive, send)
        finally:
            _actor.reset(token)
