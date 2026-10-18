"""Public routes from the widget contract. Errors are {error: {code, message}}."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from rigbox.service import RigError

router = APIRouter(prefix="/v1/rig")

_CORS_HEADERS = "Content-Type, X-Rig-Key, Accept"
_CORS_METHODS = "GET, POST, OPTIONS"


class SetupIn(BaseModel):
    product_id: str = Field(min_length=1)


class SwapIn(BaseModel):
    setup: dict[str, Any]
    role: str = ""


class AskIn(BaseModel):
    product_id: str = Field(min_length=1)
    question: str = ""
    setup: dict[str, Any] | None = None


class LinkIn(BaseModel):
    url: str = ""
    note: str = ""


class QuoteIn(BaseModel):
    setup: dict[str, Any] | None = None
    product_id: str | None = None
    contact: dict[str, Any] = Field(default_factory=dict)


class CompareIn(BaseModel):
    product_ids: list[str] = Field(min_length=1)


class FitDecision(BaseModel):
    part_sku: str = Field(min_length=1)
    fits_sku: str | None = None
    fits_family: str | None = None


def mount(app: FastAPI) -> None:
    app.include_router(router)
    app.add_exception_handler(RigError, _on_rig_error)
    app.add_exception_handler(RequestValidationError, _on_invalid)


def _service(request: Request) -> Any:
    service = getattr(request.app.state, "rig", None)
    if service is None:
        raise RigError("unavailable", "Rig is not ready.", 503)
    return service


def _origin(request: Request) -> str:
    return request.headers.get("origin") or ""


def _cors(response: Response, origin: str, allowed: bool) -> Response:
    if origin and allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Headers"] = _CORS_HEADERS
    response.headers["Access-Control-Allow-Methods"] = _CORS_METHODS
    return response


async def _auth(request: Request) -> dict[str, Any]:
    if request.method == "OPTIONS":
        return {}
    raw = request.headers.get("x-rig-key") or ""
    row = await _service(request).authenticate(raw)
    origin = _origin(request)
    if origin and origin not in (row.get("origins") or []):
        raise RigError("origin", "This shop is not allowed to use that key.", 403)
    request.state.rig_origin = origin
    request.state.rig_origin_ok = bool(origin)
    request.state.tenant_id = row["tenant_id"]
    return row


def _tenant(request: Request) -> str:
    return str(request.state.tenant_id)


async def _admin(request: Request) -> dict[str, Any]:
    raw = request.headers.get("x-rig-key") or ""
    row = await _service(request).authenticate_admin(raw)
    request.state.tenant_id = row["tenant_id"]
    request.state.rig_origin_ok = False
    return row


def _one_target(payload: FitDecision) -> tuple[str, str | None, str | None]:
    part = payload.part_sku.strip()
    sku = (payload.fits_sku or "").strip()
    family = (payload.fits_family or "").strip()
    if not part or bool(sku) == bool(family):
        raise RigError("invalid", "Name the part and either the product or the family it fits.", 422)
    return part, (sku or None), (family or None)


async def _on_rig_error(request: Request, exc: RigError) -> JSONResponse:
    response = JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}})
    origin = _origin(request)
    return _cors(response, origin, bool(getattr(request.state, "rig_origin_ok", False) and origin))


async def _on_invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
    if not request.url.path.startswith("/v1/rig"):
        raise exc
    response = JSONResponse(
        status_code=422,
        content={"error": {"code": "invalid", "message": "The request is not valid."}},
    )
    origin = _origin(request)
    return _cors(response, origin, bool(getattr(request.state, "rig_origin_ok", False) and origin))


@router.options("")
@router.options("/{rest:path}")
async def preflight(request: Request, rest: str = "") -> Response:
    del rest
    response = Response(status_code=204)
    return _cors(response, _origin(request), True)


@router.get("/search")
async def search(
    request: Request,
    q: str = "",
    limit: int = 12,
    in_stock: bool = False,
    min_price: float | None = None,
    max_price: float | None = None,
    sort: str = "",
    category: str = "",
) -> Response:
    await _auth(request)
    filters: dict[str, Any] = {}
    if in_stock:
        filters["in_stock"] = True
    if min_price is not None:
        filters["min_price"] = min_price
    if max_price is not None:
        filters["max_price_inclusive"] = max_price
    if sort:
        filters["sort"] = sort
    if category:
        filters["category"] = category
    body = await _service(request).search(_tenant(request), q, limit, filters)
    return _ok(request, body)


@router.get("/products/{product_id}")
async def product(request: Request, product_id: str) -> Response:
    await _auth(request)
    body = await _service(request).product(_tenant(request), product_id)
    return _ok(request, body)


@router.post("/setups")
async def setups(request: Request, payload: SetupIn) -> Response:
    await _auth(request)
    body = await _service(request).setups(_tenant(request), payload.product_id)
    return _ok(request, body)


@router.post("/swap")
async def swap(request: Request, payload: SwapIn) -> Response:
    await _auth(request)
    body = await _service(request).swap(_tenant(request), payload.setup, payload.role)
    return _ok(request, body)


@router.get("/graph/{product_id}")
async def graph(request: Request, product_id: str) -> Response:
    await _auth(request)
    body = await _service(request).graph(_tenant(request), product_id)
    return _ok(request, body)


@router.post("/compare")
async def compare(request: Request, payload: CompareIn) -> Response:
    await _auth(request)
    body = await _service(request).compare(_tenant(request), payload.product_ids)
    return _ok(request, body)


@router.post("/ask")
async def ask(request: Request, payload: AskIn) -> Response:
    await _auth(request)
    body = await _service(request).ask(_tenant(request), payload.product_id, payload.question, payload.setup)
    return _ok(request, body)


@router.post("/link-quote")
async def link_quote(request: Request, payload: LinkIn) -> Response:
    await _auth(request)
    body = await _service(request).link_quote(_tenant(request), payload.url, payload.note)
    return _ok(request, body)


@router.post("/quote")
async def quote(request: Request, payload: QuoteIn) -> Response:
    await _auth(request)
    client = request.client.host if request.client is not None else "unknown"
    if not _service(request).reservations.allow(client):
        raise RigError("rate_limit", "Too many reservations. Try again in a minute.", 429)
    body = await _service(request).quote(
        _tenant(request),
        {"setup": payload.setup, "product_id": payload.product_id, "contact": payload.contact},
    )
    return _ok(request, body)


@router.get("/admin/fits")
async def admin_fits(request: Request, status: str = "suggested") -> Response:
    await _admin(request)
    if status != "suggested":
        raise RigError("invalid", "Ask for suggested fits.", 422)
    body = await _service(request).suggested_fits(_tenant(request))
    return _ok(request, body)


@router.post("/admin/fits/approve")
async def admin_approve(request: Request, payload: FitDecision) -> Response:
    await _admin(request)
    part, sku, family = _one_target(payload)
    ok = await _service(request).approve(_tenant(request), part, sku, family)
    if not ok:
        raise RigError("not_found", "No such fit.", 404)
    return _ok(request, {"approved": True})


@router.post("/admin/fits/reject")
async def admin_reject(request: Request, payload: FitDecision) -> Response:
    await _admin(request)
    part, sku, family = _one_target(payload)
    ok = await _service(request).reject(_tenant(request), part, sku, family)
    if not ok:
        raise RigError("not_found", "No such fit.", 404)
    return _ok(request, {"rejected": True})


@router.post("/admin/fits/suggest")
async def admin_suggest(request: Request) -> Response:
    await _admin(request)
    body = await _service(request).suggest(_tenant(request))
    return _ok(request, body)


def _ok(request: Request, body: dict[str, Any]) -> JSONResponse:
    response = JSONResponse(body)
    return _cors(response, _origin(request), bool(getattr(request.state, "rig_origin_ok", False)))
