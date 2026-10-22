"""Admin-only delivery recovery, counters and publishable key provisioning."""

import base64
from datetime import date, datetime, timedelta, timezone
import json
import secrets
from urllib.parse import urlsplit

from fastapi import APIRouter, FastAPI, Query, Request
from pydantic import BaseModel, Field

from rigbox.api import _admin, _ok, _service, _tenant
from rigbox.service import RigError, hash_key

router = APIRouter(prefix="/v1/rig/admin")


class EmbedOrigins(BaseModel):
    origins: list[str] = Field(min_length=1, max_length=10)


@router.get("/analytics")
async def analytics(request: Request, since: date | None = None):
    await _admin(request)
    start = since or datetime.now(timezone.utc).date() - timedelta(days=30)
    counts = await _service(request).quote_store.analytics(_tenant(request), start)
    return _ok(request, {"since": start.isoformat(), "counts": counts})


@router.get("/quotes/{quote_id}/delivery")
async def delivery(request: Request, quote_id: str):
    await _admin(request)
    state = await _service(request).quote_store.status(_tenant(request), quote_id)
    if state is None:
        raise RigError("not_found", "No such request.", 404)
    return _ok(request, state)


@router.get("/quotes/attention")
async def attention(request: Request, limit: int = Query(default=100, ge=1, le=100),
                    cursor: str | None = Query(default=None, max_length=512)):
    """Staff review queue, including held quotes, without shopper contact data."""
    await _admin(request)
    after = None
    if cursor is not None:
        try:
            decoded = json.loads(base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True))
            if not isinstance(decoded, list) or len(decoded) != 2:
                raise ValueError
            stamp = datetime.fromisoformat(decoded[0])
            quote_id = decoded[1]
            if stamp.tzinfo is None or not isinstance(quote_id, str) or not 1 <= len(quote_id) <= 128 or "\x00" in quote_id:
                raise ValueError
            after = stamp, quote_id
        except (ValueError, TypeError):
            raise RigError("invalid", "That page cursor is not valid.", 422) from None
    rows = await _service(request).quote_store.attention(_tenant(request), limit=limit + 1, after=after)
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last = page[-1]
        next_cursor = base64.urlsafe_b64encode(json.dumps([last["created_at"], last["request_id"]]).encode()).decode().rstrip("=")
    return _ok(request, {"requests": page, "next_cursor": next_cursor})


@router.post("/quotes/{quote_id}/retry")
async def retry(request: Request, quote_id: str):
    await _admin(request)
    service, tenant = _service(request), _tenant(request)
    if await service.quote_store.status(tenant, quote_id) is None:
        raise RigError("not_found", "No such request.", 404)
    await service.quote_store.retry_now(tenant, quote_id)
    await service.deliver(tenant, quote_id)
    return _ok(request, await service.quote_store.status(tenant, quote_id))


@router.post("/quotes/{quote_id}/resume")
async def resume(request: Request, quote_id: str):
    """Explicit retailer action after investigating a stopped delivery."""
    await _admin(request)
    service, tenant = _service(request), _tenant(request)
    if await service.quote_store.status(tenant, quote_id) is None:
        raise RigError("not_found", "No such request.", 404)
    await service.quote_store.retry_now(tenant, quote_id, resume=True)
    await service.deliver(tenant, quote_id)
    return _ok(request, await service.quote_store.status(tenant, quote_id))


@router.post("/embed-keys")
async def embed_key(request: Request, payload: EmbedOrigins):
    await _admin(request)
    for origin in payload.origins:
        try:
            parsed = urlsplit(origin)
        except ValueError:
            raise RigError("invalid", "List exact HTTPS origins without paths.", 422) from None
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment or "*" in origin):
            raise RigError("invalid", "List exact HTTPS origins without paths.", 422)
    key = "rk_pub_" + secrets.token_hex(24)
    await _service(request).store.put_key(_tenant(request), hash_key(key), "publishable", payload.origins)
    return _ok(request, {"publishable_key": key, "origins": payload.origins})


def mount(application: FastAPI) -> None:
    application.include_router(router)
