"""Command conversation storage and worker corridor, local to this Tank box.

Identity headers are assertions from the authenticated Workspace server, never
from a browser. Worker credentials have a separate, narrowly scoped dependency.
The existing router remains the only model-call path.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/v1/command", tags=["command"])
_background: set[asyncio.Task] = set()
SQUADS = frozenset({"base", "tiger", "market_lab", "rig", "tisan", "radix", "zenas"})
TOOLS = {
    "base": ["base.batch", "base.search"],
    "tiger": ["tiger.watch", "tiger.read"],
    "market_lab": ["market_lab.research"],
    "rig": ["rig.search", "rig.ask"],
    "tisan": ["tisan.scaffold"],
    "radix": ["radix.scan"],
    "zenas": ["zenas.ask", "zenas.matters", "zenas.review"],
}
FOUNDER_TOOLS = ["skala.list", "skala.evals", "skala.approve", "skala.retire",
                 "ledger.receipts", "ledger.savings", "worker.build", "repo.read"]


def db() -> Any:
    from main import pool
    return pool()


def unpack(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def dump(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)


@dataclass(frozen=True)
class Actor:
    tenant_id: uuid.UUID
    user_id: str
    founder: bool
    squads: frozenset[str] = frozenset()


def key_matches(presented: str, expected: str) -> bool:
    return bool(presented and expected and hmac.compare_digest(presented.encode(), expected.encode()))


async def identity(request: Request) -> Actor:
    from main import TANK_API_KEY, box_region
    if not key_matches(request.headers.get("x-tank-key", ""), TANK_API_KEY):
        raise HTTPException(401, "Workspace authentication required")
    user = request.headers.get("x-tervory-user", "").strip()
    tenant = request.headers.get("x-tervory-tenant") or request.query_params.get("tenant_id")
    if not user:
        raise HTTPException(401, "Signed-in user required")
    try:
        tenant_id = uuid.UUID(tenant or "")
    except ValueError:
        raise HTTPException(422, "A tenant UUID is required") from None
    home = request.headers.get("x-tervory-home-region", box_region())
    if home != box_region():
        raise HTTPException(403, "This conversation must stay on its home box")
    admins = {s.strip() for s in os.environ.get("TERVORY_ADMIN_USER_IDS", "").split(",") if s.strip()}
    squads = frozenset(s.strip() for s in request.headers.get("x-tervory-squad", "").split(",")) & SQUADS
    return Actor(tenant_id, user, user in admins, squads)


async def worker(request: Request) -> None:
    if not key_matches(request.headers.get("x-tank-key", ""), os.environ.get("TANK_KEY_WORKERS", "")):
        raise HTTPException(401, "Worker authentication required")


def allowed_tools(actor: Actor) -> list[str]:
    squads = SQUADS if actor.founder else actor.squads
    return sorted([tool for squad in squads for tool in TOOLS[squad]] + (FOUNDER_TOOLS if actor.founder else []))


def require_tool(actor: Actor, name: str) -> None:
    if name not in allowed_tools(actor):
        raise HTTPException(403, "This tool is not available to this user")


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NewThread(Body):
    title: str = Field(default="New chat", min_length=1, max_length=200)


class Rename(Body):
    title: str = Field(min_length=1, max_length=200)


class Attachment(Body):
    name: str = Field(min_length=1, max_length=200)
    # Inline text stays in this box's Postgres; no remote URL is fetched.
    text: str = Field(max_length=200_000)


class Turn(Body):
    text: str = Field(min_length=1, max_length=20000)
    attachments: list[Attachment] = Field(default_factory=list, max_length=10)
    model: str | None = Field(default="auto", max_length=200)


class CardAction(Body):
    action: Literal["confirm", "cancel"]


class Build(Body):
    thread_id: uuid.UUID
    brief_markdown: str = Field(min_length=1, max_length=100000)


class Progress(Body):
    status: Literal["running", "done", "failed", "awaiting_review"]
    step_label: str = Field(min_length=1, max_length=500)
    pr_url: str | None = Field(default=None, max_length=500)
    ci_status: str | None = Field(default=None, max_length=100)
    review_status: str | None = Field(default=None, max_length=100)


class Followup(Body):
    followup_text: str = Field(min_length=1, max_length=20000)


async def owned(conn: Any, thread_id: uuid.UUID, actor: Actor, *, lock: bool = False) -> dict:
    row = await conn.fetchrow(
        "SELECT * FROM tank.command_threads WHERE thread_id=$1 AND tenant_id=$2 AND user_id=$3"
        + (" FOR UPDATE" if lock else ""), thread_id, actor.tenant_id, actor.user_id,
    )
    if row is None:
        raise HTTPException(404, "Thread not found")
    return dict(row)


@asynccontextmanager
async def editing(thread_id: uuid.UUID, actor: Actor):
    async with db().acquire() as conn:
        async with conn.transaction():
            row = await owned(conn, thread_id, actor, lock=True)
            state = unpack(row["state"])
            yield conn, row, state
            await conn.execute(
                "UPDATE tank.command_threads SET state=$4::jsonb, updated_at=now() "
                "WHERE thread_id=$1 AND tenant_id=$2 AND user_id=$3",
                thread_id, actor.tenant_id, actor.user_id, dump(state),
            )


async def event(conn: Any, row: dict, kind: str, payload: dict) -> dict:
    # Parent row is locked until the event commits: seq order equals commit order.
    seq = await conn.fetchval(
        "UPDATE tank.command_threads SET seq=seq+1 WHERE thread_id=$1 AND tenant_id=$2 RETURNING seq",
        row["thread_id"], row["tenant_id"],
    )
    data = {**payload, "seq": seq}
    await conn.execute(
        "INSERT INTO tank.command_events(thread_id,tenant_id,seq,kind,data) VALUES($1,$2,$3,$4,$5::jsonb)",
        row["thread_id"], row["tenant_id"], seq, kind, dump(data),
    )
    return data


async def step(conn: Any, row: dict, state: dict, payload: dict) -> None:
    state["steps"][payload["step_id"]] = payload
    await event(conn, row, "step", payload)


def receipt_row(ledger: dict, step_id: str) -> dict:
    baseline = ledger.get("baseline_cost_usd")
    baseline_model = ledger.get("baseline_model")
    pending = baseline is None or baseline_model is None
    cost = float(ledger["cost_usd"])
    return {
        "step_id": step_id, "model": ledger["model"],
        "tokens_in": ledger["tokens_in"], "tokens_out": ledger["tokens_out"],
        "cost_usd": cost, "ledger_id": str(ledger["id"]),
        "baseline_model": baseline_model if not pending else None,
        "baseline_cost_usd": float(baseline) if not pending else None,
        "saved_usd": float(baseline) - cost if not pending else None,
        "baseline_status": "baseline pending" if pending else "recorded",
    }


def totals(rows: list[dict]) -> dict:
    complete = all(r["baseline_cost_usd"] is not None for r in rows)
    return {
        "cost_usd": sum(r["cost_usd"] for r in rows),
        "baseline_cost_usd": sum(r["baseline_cost_usd"] for r in rows) if complete else None,
        "saved_usd": sum(r["saved_usd"] for r in rows) if complete else None,
    }


@router.get("/tools")
async def tools(actor: Actor = Depends(identity)) -> list[str]:
    return allowed_tools(actor)


@router.post("/threads")
async def create_thread(body: NewThread, actor: Actor = Depends(identity)) -> dict:
    thread_id = uuid.uuid4()
    state = {"messages": [], "steps": {}, "cards": {}, "receipts": [], "active_turn": None}
    async with db().acquire() as conn:
        await conn.execute(
            "INSERT INTO tank.command_threads(thread_id,tenant_id,user_id,title,state) VALUES($1,$2,$3,$4,$5::jsonb)",
            thread_id, actor.tenant_id, actor.user_id, body.title, dump(state),
        )
    return {"thread_id": str(thread_id)}


@router.get("/threads")
async def list_threads(q: str = Query(default="", max_length=200), actor: Actor = Depends(identity)) -> list[dict]:
    async with db().acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM tank.command_threads WHERE tenant_id=$1 AND user_id=$2 "
            "AND (strpos(lower(title),lower($3))>0 OR strpos(lower((state->'messages')::text),lower($3))>0) "
            "ORDER BY updated_at DESC LIMIT 100", actor.tenant_id, actor.user_id, q,
        )
    result = []
    for row in rows:
        amounts = totals(unpack(row["state"])["receipts"])
        result.append({"thread_id": str(row["thread_id"]), "title": row["title"],
                       "updated_at": row["updated_at"], "spent_usd": amounts["cost_usd"], "saved_usd": amounts["saved_usd"]})
    return result


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: uuid.UUID, actor: Actor = Depends(identity)) -> dict:
    async with db().acquire() as conn:
        row = await owned(conn, thread_id, actor)
    state = unpack(row["state"])
    amounts = totals(state["receipts"])
    return {"thread": {"thread_id": str(thread_id), "title": row["title"], "updated_at": row["updated_at"],
                       "spent_usd": amounts["cost_usd"], "saved_usd": amounts["saved_usd"]},
            "messages": state["messages"], "steps": list(state["steps"].values()),
            "cards": [{k: v for k, v in c.items() if k != "payload"} for c in state["cards"].values()],
            "receipts": state["receipts"]}


@router.patch("/threads/{thread_id}")
async def rename_thread(thread_id: uuid.UUID, body: Rename, actor: Actor = Depends(identity)) -> dict:
    async with editing(thread_id, actor) as (conn, row, state):
        await conn.execute("UPDATE tank.command_threads SET title=$4 WHERE thread_id=$1 AND tenant_id=$2 AND user_id=$3",
                           thread_id, actor.tenant_id, actor.user_id, body.title)
    return {"thread_id": str(thread_id), "title": body.title}


def sse(kind: str, data: dict) -> str:
    return f"id: {data['seq']}\nevent: {kind}\ndata: {dump(data)}\n\n"


async def replay(thread_id: uuid.UUID, actor: Actor, after: int, *, turn_id: str | None = None):
    while True:
        async with db().acquire() as conn:
            row = await owned(conn, thread_id, actor)
            events = await conn.fetch(
                "SELECT kind,data FROM tank.command_events WHERE thread_id=$1 AND tenant_id=$2 AND seq>$3 ORDER BY seq LIMIT 500",
                thread_id, actor.tenant_id, after,
            )
        for item in events:
            data = unpack(item["data"])
            after = data["seq"]
            yield sse(item["kind"], data)
        if len(events) == 500:
            continue
        if turn_id is None or unpack(row["state"]).get("active_turn") != turn_id:
            break
        yield ": waiting\n\n"
        await asyncio.sleep(0.25)


@router.get("/threads/{thread_id}/events")
async def events(thread_id: uuid.UUID, after: int = Query(default=0, ge=0), actor: Actor = Depends(identity)):
    async with db().acquire() as conn:
        await owned(conn, thread_id, actor)
    return StreamingResponse(replay(thread_id, actor, after), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def route_turn(actor: Actor, messages: list[dict]) -> Any:
    from main import Message, RouteRequest, box_region, run_route
    return await run_route(RouteRequest(tenant_id=actor.tenant_id, agent="orchestrator", task_type="command.turn",
                                       home_region=box_region(), messages=[Message(**m) for m in messages]))


async def finish_turn(thread_id: uuid.UUID, actor: Actor, turn_id: str, messages: list[dict]) -> None:
    try:
        async with asyncio.timeout(150):
            answer = await route_turn(actor, messages)
        async with editing(thread_id, actor) as (conn, row, state):
            ledger = await conn.fetchval("SELECT to_jsonb(l) FROM tank.ledger l WHERE id=$1 AND tenant_id=$2",
                                         answer.ledger_id, actor.tenant_id)
            if ledger is None:
                raise RuntimeError("Missing ledger evidence")
            receipt = receipt_row(unpack(ledger), turn_id)
            state["receipts"].append(receipt)
            state["messages"].append({"message_id": turn_id, "role": "assistant", "content": answer.content})
            # run_route currently buffers its response. Never pretend these are
            # provider token deltas; emit the complete available text once.
            await event(conn, row, "token", {"text": answer.content})
            await step(conn, row, state, {"step_id": turn_id, "label": "Answer ready", "actor": "Tervory", "status": "done"})
            await event(conn, row, "receipt", {"rows": [receipt], "totals": totals([receipt])})
            await event(conn, row, "done", {"message_id": turn_id})
            if state["active_turn"] == turn_id:
                state["active_turn"] = None
    except (Exception, asyncio.CancelledError) as exc:
        # Never return raw provider exceptions, URLs, headers or prompts.
        async with editing(thread_id, actor) as (conn, row, state):
            # Failed paid calls may have a ledger row too. Preserve its actual
            # cost without exposing the upstream exception or inventing a row.
            detail = exc.detail if isinstance(exc, HTTPException) else None
            if isinstance(detail, dict) and detail.get("ledger_id"):
                try:
                    ledger_id = uuid.UUID(str(detail["ledger_id"]))
                except ValueError:
                    ledger_id = None
                if ledger_id:
                    ledger = await conn.fetchval("SELECT to_jsonb(l) FROM tank.ledger l WHERE id=$1 AND tenant_id=$2",
                                                 ledger_id, actor.tenant_id)
                    if ledger:
                        receipt = receipt_row(unpack(ledger), turn_id)
                        state["receipts"].append(receipt)
                        await event(conn, row, "receipt", {"rows": [receipt], "totals": totals([receipt])})
            await step(conn, row, state, {"step_id": turn_id, "label": "Answer failed", "actor": "Tervory", "status": "failed"})
            await event(conn, row, "error", {"message": "The answer could not be completed. Check routing policy and service availability."})
            if state["active_turn"] == turn_id:
                state["active_turn"] = None


@router.post("/threads/{thread_id}/turn")
async def turn(thread_id: uuid.UUID, body: Turn, actor: Actor = Depends(identity)):
    if body.model not in (None, "auto"):
        from main import list_models
        if body.model not in {m["name"] for m in await list_models()}:
            raise HTTPException(422, "Model is not on the roster")
        raise HTTPException(409, "Pinned models await a router capability; choose Auto")
    turn_id = str(uuid.uuid4())
    async with editing(thread_id, actor) as (conn, row, state):
        if state["active_turn"]:
            started = datetime.fromisoformat(state["active_started_at"])
            if (datetime.now(timezone.utc) - started).total_seconds() < 180:
                raise HTTPException(409, "An answer is already running in this thread")
            # A process restart cannot leave a conversation permanently busy.
            # Do not retry a possibly charged request automatically.
            await step(conn, row, state, {"step_id": state["active_turn"], "label": "Answer interrupted",
                                          "actor": "Tervory", "status": "failed"})
            await event(conn, row, "error", {"message": "The previous answer was interrupted. It has not been retried."})
        after = row["seq"]
        state["active_turn"] = turn_id
        state["active_started_at"] = datetime.now(timezone.utc).isoformat()
        state["messages"].append({"message_id": str(uuid.uuid4()), "role": "user", "content": body.text,
                                  "attachments": [a.model_dump() for a in body.attachments]})
        # A reply is attached to the existing build, never a second build.
        if actor.founder:
            await conn.execute(
                "INSERT INTO tank.command_followups(build_id,tenant_id,followup_text) "
                "SELECT build_id,tenant_id,$3 FROM tank.command_builds WHERE thread_id=$1 AND tenant_id=$2 "
                "AND status IN ('queued','running','awaiting_review')", thread_id, actor.tenant_id, body.text,
            )
        await step(conn, row, state, {"step_id": turn_id, "label": "Preparing answer", "actor": "Tervory", "status": "running"})
        messages = [{"role": m["role"], "content": m["content"] + "".join(
            "\nAttachment " + a["name"] + ":\n" + a["text"] for a in m.get("attachments", []))} for m in state["messages"][-40:]]
    task = asyncio.create_task(finish_turn(thread_id, actor, turn_id, messages))
    _background.add(task)
    task.add_done_callback(_background.discard)
    return StreamingResponse(replay(thread_id, actor, after, turn_id=turn_id), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/build")
async def propose_build(body: Build, actor: Actor = Depends(identity)) -> dict:
    require_tool(actor, "worker.build")
    card_id = str(uuid.uuid4())
    card = {"card_id": card_id, "kind": "build", "summary": body.brief_markdown,
            "status": "pending", "payload": {"brief_markdown": body.brief_markdown}}
    async with editing(body.thread_id, actor) as (conn, row, state):
        state["cards"][card_id] = card
        await event(conn, row, "card", {k: v for k, v in card.items() if k != "payload"})
    return {k: v for k, v in card.items() if k != "payload"}


@router.post("/cards/{card_id}")
async def card_action(card_id: uuid.UUID, body: CardAction, actor: Actor = Depends(identity)) -> dict:
    async with db().acquire() as conn:
        thread_id = await conn.fetchval(
            "SELECT thread_id FROM tank.command_threads WHERE tenant_id=$1 AND user_id=$2 AND state->'cards' ? $3",
            actor.tenant_id, actor.user_id, str(card_id),
        )
    if thread_id is None:
        raise HTTPException(404, "Card not found")
    async with editing(thread_id, actor) as (conn, row, state):
        card = state["cards"][str(card_id)]
        target = "confirmed" if body.action == "confirm" else "cancelled"
        if card["status"] != "pending":
            if card["status"] != target:
                raise HTTPException(409, "Card has already been resolved")
            return {k: v for k, v in card.items() if k != "payload"}
        if body.action == "confirm":
            require_tool(actor, "worker.build")
            if card["kind"] != "build":
                raise HTTPException(409, "This action is not implemented")
            open_build = await conn.fetchval(
                "SELECT build_id FROM tank.command_builds WHERE thread_id=$1 AND tenant_id=$2 "
                "AND status IN ('queued','running','awaiting_review')", thread_id, actor.tenant_id,
            )
            if open_build:
                raise HTTPException(409, "Reply to the existing build before starting another")
            build_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO tank.command_builds(build_id,thread_id,tenant_id,user_id,brief_markdown,status) "
                "VALUES($1,$2,$3,$4,$5,'queued')", build_id, thread_id, actor.tenant_id, actor.user_id, card["payload"]["brief_markdown"],
            )
            card["build_id"] = str(build_id)
            await step(conn, row, state, {"step_id": str(build_id), "label": "Build queued", "actor": "worker", "status": "planned"})
        card["status"] = target
        result = {k: v for k, v in card.items() if k != "payload"}
        await event(conn, row, "card", result)
        return result


@router.get("/builds/next", dependencies=[Depends(worker)])
async def next_build() -> dict | None:
    async with db().acquire() as conn:
        async with conn.transaction():
            # Workers are a platform principal. Claim one row across tenants;
            # all subsequent reads and writes use that row's tenant.
            build = await conn.fetchrow(
                "SELECT b.* FROM tank.command_builds b JOIN tank.command_threads t "
                "ON t.thread_id=b.thread_id AND t.tenant_id=b.tenant_id "
                "WHERE b.status='queued' ORDER BY b.created_at LIMIT 1 FOR UPDATE OF t SKIP LOCKED"
            )
            if build is None:
                return None
            # Match the thread-then-build lock order used by progress/confirm.
            row = await owned(conn, build["thread_id"], Actor(build["tenant_id"], build["user_id"], True), lock=True)
            state = unpack(row["state"])
            claimed = await conn.fetchval(
                "UPDATE tank.command_builds SET status='running',updated_at=now() "
                "WHERE build_id=$1 AND tenant_id=$2 AND status='queued' RETURNING build_id",
                build["build_id"], build["tenant_id"],
            )
            if claimed is None:
                return None
            await step(conn, row, state, {"step_id": str(build["build_id"]), "label": "Build started",
                                          "actor": "worker", "status": "running"})
            await conn.execute("UPDATE tank.command_threads SET state=$3::jsonb,updated_at=now() WHERE thread_id=$1 AND tenant_id=$2",
                               build["thread_id"], build["tenant_id"], dump(state))
            return {**dict(build), "status": "running"}


async def build_record(conn: Any, build_id: uuid.UUID) -> dict:
    # Only the worker corridor calls this unscoped lookup. Its key grants all
    # build jobs on this box, never conversation routes or another region.
    row = await conn.fetchrow("SELECT * FROM tank.command_builds WHERE build_id=$1", build_id)
    if row is None:
        raise HTTPException(404, "Build not found")
    return dict(row)


@router.post("/builds/{build_id}/progress", dependencies=[Depends(worker)])
async def progress(build_id: uuid.UUID, body: Progress) -> dict:
    if body.pr_url:
        from urllib.parse import urlsplit
        parsed = urlsplit(body.pr_url)
        if (parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.query or parsed.fragment
                or not re.fullmatch(r"/Tervory-AI/tervory-tank/pull/[1-9][0-9]*", parsed.path)):
            raise HTTPException(422, "A repository pull request URL is required")
    async with db().acquire() as conn:
        build = await build_record(conn, build_id)
    actor = Actor(build["tenant_id"], build["user_id"], True)
    async with editing(build["thread_id"], actor) as (conn, row, state):
        current = await conn.fetchrow("SELECT * FROM tank.command_builds WHERE build_id=$1 AND tenant_id=$2 FOR UPDATE", build_id, actor.tenant_id)
        if current["status"] == "queued":
            raise HTTPException(409, "Claim the build before reporting progress")
        if current["status"] in {"done", "failed"} and current["status"] != body.status:
            raise HTTPException(409, "Build is already finished")
        await conn.execute(
            "UPDATE tank.command_builds SET status=$3,pr_url=coalesce($4,pr_url),ci_status=coalesce($5,ci_status),"
            "review_status=coalesce($6,review_status),updated_at=now() WHERE build_id=$1 AND tenant_id=$2",
            build_id, actor.tenant_id, body.status, body.pr_url, body.ci_status, body.review_status,
        )
        status = "running" if body.status == "awaiting_review" else body.status
        payload = {"step_id": str(build_id), "label": body.step_label, "actor": "worker", "status": status,
                   "link": body.pr_url or current["pr_url"], "ci_status": body.ci_status or current["ci_status"],
                   "review_status": body.review_status or current["review_status"]}
        await step(conn, row, state, payload)
    return payload


@router.post("/builds/{build_id}/followups")
async def add_followup(build_id: uuid.UUID, body: Followup, actor: Actor = Depends(identity)) -> dict:
    require_tool(actor, "worker.build")
    async with db().acquire() as conn:
        async with conn.transaction():
            build = await conn.fetchrow(
                "SELECT * FROM tank.command_builds WHERE build_id=$1 AND tenant_id=$2 AND user_id=$3 FOR UPDATE",
                build_id, actor.tenant_id, actor.user_id,
            )
            if build is None:
                raise HTTPException(404, "Build not found")
            if build["status"] not in {"queued", "running", "awaiting_review"}:
                raise HTTPException(409, "Build is already finished")
            followup_id = await conn.fetchval(
                "INSERT INTO tank.command_followups(build_id,tenant_id,followup_text) VALUES($1,$2,$3) RETURNING followup_id",
                build_id, actor.tenant_id, body.followup_text,
            )
    return {"followup_id": followup_id}


@router.get("/builds/{build_id}/followups", dependencies=[Depends(worker)])
async def get_followups(build_id: uuid.UUID, after: int = Query(default=0, ge=0)) -> list[dict]:
    # Cursor replay is lossless; reads never delete or acknowledge work.
    async with db().acquire() as conn:
        build = await build_record(conn, build_id)
        rows = await conn.fetch(
            "SELECT followup_id,followup_text FROM tank.command_followups WHERE build_id=$1 AND tenant_id=$2 "
            "AND followup_id>$3 ORDER BY followup_id", build_id, build["tenant_id"], after,
        )
    return [dict(row) for row in rows]
