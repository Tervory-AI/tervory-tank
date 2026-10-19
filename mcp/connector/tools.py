"""The six connector tools. Each call carries the signed-in tenant and no other."""

from __future__ import annotations

import ipaddress
import json
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from connector.tank import Tank, TankError

EVERY = ("15m", "1h", "6h", "1d", "7d")
_JURISDICTION = {
    "us": "us",
    "usa": "us",
    "united states": "us",
    "za": "za",
    "sa": "za",
    "south africa": "za",
}


@dataclass(frozen=True)
class Caller:
    user_id: str
    org_id: str
    tenant_id: str


@dataclass(frozen=True)
class ToolSpec:
    name: str
    title: str
    description: str
    read_only: bool
    schema: dict[str, Any]


def _object(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="rig_search",
        title="Search a catalogue",
        description=(
            "Search the signed-in account's own retailer catalogue for a product name, brand, or sku. "
            "Returns only the matches Tank has for that account."
        ),
        read_only=True,
        schema=_object(
            {
                "query": {"type": "string", "minLength": 1, "maxLength": 200},
                "limit": {"type": "integer", "minimum": 1, "maximum": 24},
            },
            ["query"],
        ),
    ),
    ToolSpec(
        name="base_lookup",
        title="Look up records",
        description=(
            "Look up the signed-in account's own enriched business records. "
            "An optional query keeps rows whose text contains those words. An optional batch keeps one batch."
        ),
        read_only=True,
        schema=_object(
            {
                "query": {"type": "string", "maxLength": 200},
                "batch": {"type": "string", "maxLength": 120},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            [],
        ),
    ),
    ToolSpec(
        name="base_enrich",
        title="Enrich a list",
        description=(
            "Submit up to 100 business rows for enrichment on the signed-in account. "
            "Returns a batch id. This adds those rows to that account."
        ),
        read_only=False,
        schema=_object(
            {
                "records": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 100,
                    "items": {"type": "object"},
                },
                "batch": {"type": "string", "minLength": 1, "maxLength": 120},
                "engine": {"type": "string", "maxLength": 40},
            },
            ["records"],
        ),
    ),
    ToolSpec(
        name="zenas_research",
        title="Research a legal question",
        description=(
            "Ask a business-law question for the United States or South Africa. "
            "A scope check runs first. Criminal law is refused. "
            "An allowed question returns the passages Tank found, with their citations."
        ),
        read_only=True,
        schema=_object(
            {
                "question": {"type": "string", "minLength": 1, "maxLength": 2000},
                "jurisdiction": {"type": "string", "enum": ["us", "za", "US", "ZA", "SA"]},
            },
            ["question", "jurisdiction"],
        ),
    ),
    ToolSpec(
        name="market_lab_brief",
        title="Write a market brief",
        description=(
            "Ask for a short sourced brief on one market topic for the signed-in account. "
            "Claims that carry a source URL and a date are returned with that source."
        ),
        read_only=True,
        schema=_object(
            {"topic": {"type": "string", "minLength": 1, "maxLength": 500}},
            ["topic"],
        ),
    ),
    ToolSpec(
        name="tiger_watch",
        title="Watch a price",
        description=(
            "Add a public product page to the signed-in account's price watchlist. "
            "This changes that account's watchlist."
        ),
        read_only=False,
        schema=_object(
            {
                "url": {"type": "string", "minLength": 1, "maxLength": 2000},
                "label": {"type": "string", "maxLength": 200},
                "every": {"type": "string", "enum": list(EVERY)},
                "threshold_percent": {"type": "number", "minimum": 0, "maximum": 10000},
            },
            ["url"],
        ),
    ),
)

_BY_NAME = {tool.name: tool for tool in TOOLS}


def list_tools() -> list[dict[str, Any]]:
    listed: list[dict[str, Any]] = []
    for tool in TOOLS:
        hint: dict[str, Any] = {"title": tool.title}
        if tool.read_only:
            hint["readOnlyHint"] = True
        else:
            hint["destructiveHint"] = True
        listed.append(
            {
                "name": tool.name,
                "title": tool.title,
                "description": tool.description,
                "inputSchema": tool.schema,
                "annotations": hint,
            }
        )
    return listed


def _text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _args(raw: Any) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def _fail(message: str) -> dict[str, Any]:
    return {"ok": False, "message": message, "sources": [], "model": "", "cost_usd": 0}


def _cost(payload: Any) -> float:
    if not isinstance(payload, dict):
        return 0.0
    try:
        return round(float(payload.get("_cost_usd") or payload.get("cost_usd") or 0), 6)
    except (TypeError, ValueError):
        return 0.0


def _model_name(payload: Any, cost: float) -> str:
    if isinstance(payload, dict):
        model = payload.get("model")
        if isinstance(model, str) and model.strip():
            return model.strip()
    return "code" if cost == 0 else ""


def _envelope(body: dict[str, Any], *, sources: list[dict[str, Any]], model: str, cost: float) -> dict[str, Any]:
    body["sources"] = sources
    body["model"] = model
    body["cost_usd"] = round(cost, 6)
    return body


def _jurisdiction(value: Any) -> str | None:
    return _JURISDICTION.get(str(value or "").strip().lower())


def _public_host(host: str) -> bool:
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local") or host.endswith(".internal"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "." in host
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _public_page(value: str) -> str | None:
    text = value.strip()
    if not text or len(text) > 2000:
        return None
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return None
    if not host or not _public_host(host):
        return None
    return text


def _date(value: str) -> str:
    text = value.strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    if len(text) == 7 and text[4] == "-":
        return text + "-01"
    return ""


def citations_from_text(text: str) -> list[dict[str, str]]:
    """CLAIM / URL / DATE lines, the shape Market Lab asks the model to use."""
    found: list[dict[str, str]] = []
    claim = url = stamp = ""
    for line in text.splitlines():
        piece = line.strip()
        upper = piece.upper()
        if upper.startswith("CLAIM:"):
            if claim and url.startswith("http") and _date(stamp):
                found.append({"claim": claim, "url": url, "date": _date(stamp)})
            claim = piece.split(":", 1)[1].strip()
            url = ""
            stamp = ""
        elif upper.startswith("URL:"):
            url = piece.split(":", 1)[1].strip()
        elif upper.startswith("DATE:"):
            stamp = piece.split(":", 1)[1].strip()
    if claim and url.startswith("http") and _date(stamp):
        found.append({"claim": claim, "url": url, "date": _date(stamp)})
    return found


def research_prompt(question: str) -> str:
    return (
        "Answer in short claims. For each claim use three lines: "
        "CLAIM, URL, DATE. Every claim needs a source URL and a date. "
        "Question: " + question.strip()
    )


def _scope_allows(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("criminal") is True:
        return False
    return payload.get("in_scope") is True


async def _run(caller: Caller, tank: Tank, name: str, args: dict[str, Any]) -> dict[str, Any]:
    try:
        if name == "rig_search":
            return await _rig_search(caller, tank, args)
        if name == "base_lookup":
            return await _base_lookup(caller, tank, args)
        if name == "base_enrich":
            return await _base_enrich(caller, tank, args)
        if name == "zenas_research":
            return await _zenas_research(caller, tank, args)
        if name == "market_lab_brief":
            return await _market_lab_brief(caller, tank, args)
        if name == "tiger_watch":
            return await _tiger_watch(caller, tank, args)
    except TankError as exc:
        return _fail(exc.detail or "Tank refused the call.")
    return _fail("That tool is not on this server.")


async def call_tool(name: str, caller: Caller, tank: Tank, arguments: Any) -> dict[str, Any]:
    if name not in _BY_NAME:
        return _fail("That tool is not on this server.")
    return await _run(caller, tank, name, _args(arguments))


async def _rig_search(caller: Caller, tank: Tank, args: dict[str, Any]) -> dict[str, Any]:
    query = _text(args.get("query"), 200)
    if not query:
        return _fail("Enter a product name, brand, or sku.")
    try:
        limit = int(args.get("limit") or 12)
    except (TypeError, ValueError):
        return _fail("Limit has to be a number from 1 to 24.")
    if limit < 1 or limit > 24:
        return _fail("Limit has to be a number from 1 to 24.")
    payload = await tank.call(
        "POST",
        "/v1/skala/rig.search/run",
        body={
            "tenant_id": caller.tenant_id,
            "input": {"q": query, "limit": limit, "tenant_id": caller.tenant_id},
        },
    )
    results = payload.get("results") if isinstance(payload, dict) else None
    rows = [row for row in results if isinstance(row, dict)] if isinstance(results, list) else []
    cost = _cost(payload)
    sources = []
    for row in rows:
        title = str(row.get("name") or row.get("id") or "Product")
        detail = str(row.get("id") or "")
        sources.append({"title": title, "detail": detail})
    return _envelope(
        {"query": query, "results": rows},
        sources=sources,
        model=_model_name(payload, cost),
        cost=cost,
    )


async def _base_lookup(caller: Caller, tank: Tank, args: dict[str, Any]) -> dict[str, Any]:
    query = _text(args.get("query"), 200).casefold()
    batch = _text(args.get("batch"), 120)
    try:
        limit = int(args.get("limit") or 20)
    except (TypeError, ValueError):
        return _fail("Limit has to be a number from 1 to 50.")
    if limit < 1 or limit > 50:
        return _fail("Limit has to be a number from 1 to 50.")
    params = {"tenant_id": caller.tenant_id, "limit": "200", "offset": "0"}
    if batch:
        params["batch"] = batch
    payload = await tank.call("GET", "/v1/base/records", params=params)
    rows = payload if isinstance(payload, list) else []
    kept: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        summary = _summarize_record(row)
        if query and query not in json.dumps(summary, default=str).casefold():
            continue
        kept.append(summary)
        profile = row.get("profile") if isinstance(row.get("profile"), dict) else {}
        for field, item in profile.items():
            if isinstance(item, dict) and item.get("source"):
                sources.append({"title": str(field), "detail": str(item.get("source"))})
        if len(kept) >= limit:
            break
    return _envelope(
        {"records": kept},
        sources=sources[:40],
        model="code",
        cost=0,
    )


def _summarize_record(row: dict[str, Any]) -> dict[str, Any]:
    profile = row.get("profile") if isinstance(row.get("profile"), dict) else {}
    fields: dict[str, Any] = {}
    for key, item in list(profile.items())[:12]:
        fields[str(key)] = item.get("value") if isinstance(item, dict) else item
    return {
        "id": row.get("id"),
        "batch": row.get("batch"),
        "status": row.get("status"),
        "confidence": row.get("confidence"),
        "fields": fields,
    }


async def _base_enrich(caller: Caller, tank: Tank, args: dict[str, Any]) -> dict[str, Any]:
    records = args.get("records")
    if not isinstance(records, list) or not records:
        return _fail("Add at least one row.")
    if len(records) > 100:
        return _fail("Send at most 100 rows.")
    clean: list[dict[str, Any]] = []
    for index, row in enumerate(records, start=1):
        if not isinstance(row, dict) or not row:
            return _fail(f"Row {index} needs to be an object with at least one field.")
        encoded = json.dumps(row, default=str)
        if len(encoded) > 20000:
            return _fail(f"Row {index} is too long.")
        clean.append(json.loads(encoded))
    batch = _text(args.get("batch"), 120) or f"mcp-{uuid.uuid4()}"
    body: dict[str, Any] = {
        "tenant_id": caller.tenant_id,
        "created_by": caller.user_id,
        "batch": batch,
        "records": clean,
        "preview": False,
    }
    engine = _text(args.get("engine"), 40)
    if engine:
        body["engine"] = engine
    payload = await tank.call("POST", "/v1/base/run", body=body)
    task = payload.get("task") if isinstance(payload, dict) else None
    task_id = task.get("id") if isinstance(task, dict) else None
    return _envelope(
        {"batch_id": batch, "task_id": task_id, "records": len(clean)},
        sources=[{"title": "Batch", "detail": batch}],
        model="code",
        cost=0,
    )


async def _zenas_research(caller: Caller, tank: Tank, args: dict[str, Any]) -> dict[str, Any]:
    question = _text(args.get("question"), 2000)
    if not question:
        return _fail("Enter a legal question.")
    jurisdiction = _jurisdiction(args.get("jurisdiction"))
    if jurisdiction is None:
        return _fail("Choose US or SA.")
    scope = await tank.call(
        "POST",
        "/v1/skala/zenas.scope/run",
        body={
            "tenant_id": caller.tenant_id,
            "input": {"text": question, "jurisdiction": jurisdiction},
        },
    )
    cost = _cost(scope)
    decision = scope if isinstance(scope, dict) else {}
    reason = str(decision.get("reason") or "Not in scope.")
    if not _scope_allows(decision):
        return _envelope(
            {"answer": reason, "scope": _public_scope(decision), "passages": []},
            sources=[],
            model=_model_name(scope, cost),
            cost=cost,
        )
    found = await tank.call(
        "POST",
        "/v1/skala/zenas.retrieve/run",
        body={
            "tenant_id": caller.tenant_id,
            "input": {"query": question, "jurisdiction": jurisdiction},
        },
    )
    cost = round(cost + _cost(found), 6)
    passages = found.get("passages") if isinstance(found, dict) else None
    rows = [row for row in passages if isinstance(row, dict)] if isinstance(passages, list) else []
    sources = []
    lines = []
    for row in rows[:12]:
        title = str(row.get("citation") or row.get("heading") or "Passage")
        detail = str(row.get("text") or row.get("heading") or "")[:240]
        sources.append({"title": title, "detail": detail})
        lines.append(title)
    if lines:
        answer = reason + " " + " ".join(lines)
    else:
        answer = reason + " No passage was returned for this question."
    return _envelope(
        {"answer": answer.strip(), "scope": _public_scope(decision), "passages": rows[:12]},
        sources=sources,
        model=_model_name(found, _cost(found)) if _cost(found) else _model_name(scope, cost),
        cost=cost,
    )


def _public_scope(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "in_scope": bool(decision.get("in_scope")),
        "criminal": bool(decision.get("criminal")),
        "jurisdiction": decision.get("jurisdiction") or "",
        "area": decision.get("area") or "",
        "reason": str(decision.get("reason") or ""),
    }


async def _market_lab_brief(caller: Caller, tank: Tank, args: dict[str, Any]) -> dict[str, Any]:
    topic = _text(args.get("topic"), 500)
    if not topic:
        return _fail("Enter a market topic.")
    payload = await tank.call(
        "POST",
        "/v1/route",
        body={
            "tenant_id": caller.tenant_id,
            "agent": "market_lab",
            "task_type": "market.research",
            "messages": [{"role": "user", "content": research_prompt(topic)}],
        },
    )
    content = str(payload.get("content") or "") if isinstance(payload, dict) else ""
    cites = citations_from_text(content)
    claims = [item["claim"] for item in cites]
    answer = " ".join(claims) if claims else content
    sources = [{"title": item["claim"], "url": item["url"], "detail": item["date"]} for item in cites]
    cost = _cost(payload)
    return _envelope(
        {"topic": topic, "answer": answer},
        sources=sources,
        model=_model_name(payload, cost),
        cost=cost,
    )


async def _tiger_watch(caller: Caller, tank: Tank, args: dict[str, Any]) -> dict[str, Any]:
    url = _public_page(str(args.get("url") or ""))
    if url is None:
        return _fail("That address cannot be checked. Use a public http or https page.")
    label = _text(args.get("label"), 200)
    every = _text(args.get("every"), 8) or "1d"
    if every not in EVERY:
        return _fail("Choose how often to check: 15m, 1h, 6h, 1d, or 7d.")
    try:
        percent = float(args.get("threshold_percent") if args.get("threshold_percent") is not None else 0)
    except (TypeError, ValueError):
        return _fail("The alert percent has to be zero or more.")
    if percent < 0 or percent > 10000:
        return _fail("The alert percent has to be zero or more.")
    threshold = round(percent * 1000) / 100000
    payload = await tank.call(
        "POST",
        "/v1/tiger/watchlist",
        body={
            "tenant_id": caller.tenant_id,
            "url": url,
            "label": label,
            "every": every,
            "threshold": threshold,
            "enabled": True,
            "engine": "",
        },
    )
    watch = payload if isinstance(payload, dict) else {}
    title = label or url
    return _envelope(
        {
            "id": watch.get("id"),
            "url": watch.get("url") or url,
            "label": watch.get("label") if watch.get("label") is not None else label,
            "every": watch.get("every") or every,
        },
        sources=[{"title": title, "url": url}],
        model="code",
        cost=0,
    )


def render(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, default=str)
    if len(text) <= 100_000:
        return text
    short = {
        "sources": list(payload.get("sources") or [])[:20],
        "model": payload.get("model") or "",
        "cost_usd": payload.get("cost_usd") or 0,
        "answer": "The result was too long. Ask for a smaller list.",
    }
    return json.dumps(short)
