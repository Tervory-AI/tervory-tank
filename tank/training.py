"""Local collection, scheduled re-tests and optional private exports.

The background collector reads only existing accepted/released sources. Rooms
need no hooks and keep their own credentials. Exports preserve reviewed content.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException

from gold import (PLATFORM_TENANT, Reviewer, add_candidate, encoded, input_hash,
                  obj, require_job, require_reviewer, runtime, is_holdout)

log = logging.getLogger("tank.training")


async def save_pair(conn, *, tenant: uuid.UUID, agent: str, task: str, value: Any,
                    output: Any, approved_by: str, source: str, ref: str,
                    gold_id: uuid.UUID | None = None, holdout: bool = False,
                    client_matter: bool = False) -> None:
    await conn.execute(
        """INSERT INTO tank.training_pairs
        (tenant_id,agent,task_type,region,input,output,approved_by,source,source_ref,gold_id,holdout,client_matter)
        VALUES ($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7,$8,$9,$10,$11,$12)
        ON CONFLICT (tenant_id,region,source,source_ref) DO NOTHING""",
        tenant, agent, task, runtime().box_region(), encoded(value), encoded(output),
        approved_by, source, ref, gold_id, holdout, client_matter,
    )


async def pair_from_gold(conn, row: dict[str, Any]) -> None:
    await save_pair(conn, tenant=row["tenant_id"], agent=row["agent"], task=row["skill_id"],
                    value=obj(row["input"]), output=obj(row["expected"]), approved_by=row["checked_by"],
                    source="gold", ref=str(row["id"]), gold_id=row["id"], holdout=row["holdout"],
                    client_matter=row["agent"] == "zenas" and row["tenant_id"] != PLATFORM_TENANT)


async def collect_ledger(conn, tenant: uuid.UUID) -> None:
    import graduate
    region = runtime().box_region()
    # A later rejection revokes both the candidate and its training provenance.
    await conn.execute(
        """UPDATE tank.training_pairs p SET active=false
        WHERE p.tenant_id=$1 AND p.region=$2 AND p.source IN ('ledger','gold')
        AND EXISTS (SELECT 1 FROM tank.gold_examples g JOIN tank.ledger l
          ON g.source='ledger' AND g.source_ref=l.id::text AND g.tenant_id=l.tenant_id
          WHERE g.tenant_id=$1 AND g.region=$2
          AND (p.gold_id=g.id OR (p.source='ledger' AND p.source_ref=g.source_ref))
          AND (l.feedback IS DISTINCT FROM 'accepted' OR l.outcome<>'delivered'))""", tenant, region,
    )
    await conn.execute(
        """UPDATE tank.gold_examples g SET status='rejected'
        WHERE g.tenant_id=$1 AND g.region=$2 AND g.source='ledger'
        AND EXISTS (SELECT 1 FROM tank.ledger l WHERE l.id::text=g.source_ref AND l.tenant_id=$1
        AND (l.feedback IS DISTINCT FROM 'accepted' OR l.outcome<>'delivered'))""", tenant, region,
    )
    rows = await conn.fetch(
        """SELECT l.id,l.agent,l.skill,l.task_type,l.feedback_by,t.messages,t.content
        FROM tank.ledger l JOIN tank.transcripts t ON t.ledger_id=l.id AND t.tenant_id=l.tenant_id
        WHERE l.tenant_id=$1 AND l.region=$2 AND l.feedback='accepted' AND l.outcome='delivered'
        AND NOT EXISTS (SELECT 1 FROM tank.training_pairs p
          WHERE p.tenant_id=$1 AND p.region=$2 AND p.source='ledger' AND p.source_ref=l.id::text)
        ORDER BY l.ts LIMIT 500""", tenant, region,
    )
    for row in rows:
        value = graduate.skill_payload(obj(row["messages"]))
        output = graduate.as_obj(row["content"]) or {"text": row["content"]}
        skill = (row["skill"] or row["task_type"]).split("@", 1)[0]
        gold_id = await add_candidate(conn, tenant=tenant, skill=skill, agent=row["agent"],
                                      value=value, expected=output, source="ledger", ref=str(row["id"]))
        from gold import is_holdout
        await save_pair(conn, tenant=tenant, agent=row["agent"], task=row["task_type"],
                        value=value, output=output, approved_by=row["feedback_by"] or "client",
                        source="ledger", ref=str(row["id"]), gold_id=gold_id,
                        holdout=is_holdout(tenant, skill, value), client_matter=row["agent"] == "zenas")


async def collect_zenas(conn, tenant: uuid.UUID | None) -> None:
    region = runtime().box_region()
    rows = await conn.fetch(
        """SELECT p.*,r.reviewer FROM agent_zenas.training_pairs p
        JOIN agent_zenas.worked_matters w ON w.id=p.worked_id AND w.region=p.region
          AND w.tenant_id IS NOT DISTINCT FROM p.tenant_id
        LEFT JOIN LATERAL (
          SELECT r.reviewer FROM agent_zenas.reviews r
          JOIN agent_zenas.documents d ON d.id=r.document_id AND d.tenant_id=r.tenant_id
          WHERE d.matter_id=w.released_matter_id AND d.tenant_id=p.tenant_id
          AND d.state='released' AND r.decision='released' ORDER BY r.ts DESC LIMIT 1
        ) r ON true
        WHERE p.tenant_id IS NOT DISTINCT FROM $1::uuid AND p.region=$2
        AND ((p.source='case' AND w.source='case' AND w.material_type='public_record')
             OR (p.source='released' AND w.source='released' AND r.reviewer IS NOT NULL))
        AND NOT EXISTS (SELECT 1 FROM tank.training_pairs t WHERE t.tenant_id=coalesce($1::uuid,$3)
          AND t.region=$2 AND t.source='zenas' AND t.source_ref=p.id::text)
        ORDER BY p.created_at LIMIT 500""", tenant, region, PLATFORM_TENANT,
    )
    for row in rows:
        value = {"text": row["request"]}
        output = {"findings": obj(row["findings"]), "outcome": row["outcome"],
                  "memo": row["memo"], "lawyer_edits": row["lawyer_edits"]}
        scope = tenant or PLATFORM_TENANT
        # These are legal reasoning examples, not synthetic inputs to an unrelated
        # registered skill. A reviewer can inspect them under zenas.reasoning.
        skill = "zenas.reasoning"
        gold_id = await add_candidate(conn, tenant=scope, skill=skill, agent="zenas", value=value,
                                      expected=output, source="zenas", ref=str(row["id"]))
        from gold import is_holdout
        await save_pair(conn, tenant=scope, agent="zenas", task=skill, value=value, output=output,
                        approved_by=row["reviewer"] or "decided case", source="zenas", ref=str(row["id"]),
                        gold_id=gold_id, holdout=is_holdout(scope, skill, value),
                        client_matter=row["source"] == "released")


async def collect_fits(conn, tenant: uuid.UUID) -> None:
    rows = await conn.fetch(
        """SELECT * FROM agent_rig.fits WHERE tenant_id=$1 AND approved AND source<>'rejected'""", tenant,
    )
    current = []
    for row in rows:
        value = {"part_sku": row["part_sku"], "fits_sku": row["fits_sku"], "fits_family": row["fits_family"]}
        expected = {"approved": True, "rule": obj(row["rule"]), "note": row["note"]}
        ref = input_hash([value, expected])
        current.append(ref)
        await add_candidate(conn, tenant=tenant, skill="rig.fit", agent="rig", value=value,
                            expected=expected, source="rig", ref=ref)
    await conn.execute(
        """UPDATE tank.gold_examples SET status='rejected'
        WHERE tenant_id=$1 AND region=$2 AND source='rig' AND NOT (source_ref=ANY($3::text[]))""",
        tenant, runtime().box_region(), current,
    )
    await conn.execute(
        """UPDATE tank.training_pairs p SET active=false WHERE p.tenant_id=$1 AND p.region=$2
        AND EXISTS (SELECT 1 FROM tank.gold_examples g WHERE g.id=p.gold_id AND g.tenant_id=$1
          AND g.region=$2 AND g.source='rig' AND g.status='rejected')""", tenant, runtime().box_region(),
    )


async def collect_once() -> None:
    rt = runtime()
    async with rt.pool().acquire() as conn:
        if not await conn.fetchval("SELECT pg_try_advisory_lock(871222)"):
            return
        try:
            # Tenant discovery is internal maintenance, never a response or export.
            tenants = await conn.fetch("SELECT DISTINCT tenant_id FROM tank.ledger WHERE region=$1", rt.box_region())
            for row in tenants:
                async with conn.transaction():
                    await collect_ledger(conn, row["tenant_id"])
            if await conn.fetchval("SELECT to_regclass('agent_zenas.training_pairs')"):
                tenants = await conn.fetch(
                    "SELECT DISTINCT tenant_id FROM agent_zenas.training_pairs WHERE region=$1", rt.box_region(),
                )
                for row in tenants:
                    async with conn.transaction():
                        await collect_zenas(conn, row["tenant_id"])
            if await conn.fetchval("SELECT to_regclass('agent_rig.fits')"):
                for row in await conn.fetch("SELECT DISTINCT tenant_id FROM agent_rig.fits"):
                    async with conn.transaction():
                        await collect_fits(conn, row["tenant_id"])
        finally:
            await conn.execute("SELECT pg_advisory_unlock(871222)")



ROOMS = ("base", "tiger", "market_lab", "rig", "zenas", "radix", "tisan")


def valid_auto_candidate(row: Any, room: str, region: str) -> bool:
    """Fail closed on provenance and region before anything is persisted."""
    return (isinstance(row, dict) and row.get("public") is True
            and row.get("client_matter", False) is False
            and row.get("tenant_id") in (None, str(PLATFORM_TENANT))
            and region in ("us-east", "za") and row.get("region") == region
            and isinstance(row.get("skill_id"), str)
            and row["skill_id"].startswith({"market_lab": ("market.",), "radix": ("radix.", "scan.")}.get(room, (room + ".",)))
            and isinstance(row.get("label_source"), str)
            and 0 < len(row["label_source"]) <= 500
            and "input" in row and "expected" in row)


async def collect_room_gold(day: date) -> None:
    region = runtime().box_region()
    if region not in ("us-east", "za"):
        return
    limit = max(0, int(os.environ.get("GOLD_AUTO_MAX") or "200"))
    if not limit:
        return
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        for room in ROOMS:
            key = os.environ.get(f"TANK_KEY_{room.upper()}", "")
            if not key:
                continue
            # Fixed local destinations: a room can never redirect its key elsewhere.
            host = "agent-" + room.replace("_", "-")
            try:
                response = await client.get(f"http://{host}:8000/gold/candidates",
                                            params={"limit": min(limit, 200)},
                                            headers={"X-Tank-Key": key})
                if response.status_code in (404, 405, 501):
                    continue
                response.raise_for_status()
                rows = response.json()
                if not isinstance(rows, list):
                    continue
            except (httpx.HTTPError, ValueError):
                log.warning("Room gold intake unavailable: %s", room)
                continue
            async with runtime().pool().acquire() as conn, conn.transaction():
                # Serialise retries/manual runs and enforce a durable per-source daily cap.
                await conn.execute("SELECT pg_advisory_xact_lock(871226)")
                for row in rows[:200]:
                    if not valid_auto_candidate(row, room, region):
                        continue
                    source = row["label_source"]
                    used = await conn.fetchval(
                        """SELECT count(*) FROM tank.gold_examples
                        WHERE tenant_id=$1 AND region=$2 AND agent=$3
                        AND auto_label AND intake_day=$4""",
                        PLATFORM_TENANT, region, room, day,
                    )
                    if used >= limit:
                        continue
                    await conn.execute(
                        """INSERT INTO tank.gold_examples
                        (tenant_id,region,skill_id,agent,input,expected,source,source_ref,
                         input_hash,holdout,auto_label,label_source,public,intake_day)
                        VALUES ($1,$2,$3,$4,$5::jsonb,$6::jsonb,'room_auto',$7,$8,$9,true,$10,true,$11)
                        ON CONFLICT (tenant_id,region,skill_id,source,source_ref) DO NOTHING""",
                        PLATFORM_TENANT, region, row["skill_id"], room,
                        encoded(row["input"]), encoded(row["expected"]),
                        input_hash([source, row["input"], row["expected"]]), input_hash(row["input"]),
                        is_holdout(PLATFORM_TENANT, row["skill_id"], row["input"]),
                        source, day,
                    )
                    from gold import settle_auto_source
                    await settle_auto_source(conn, {"tenant_id": PLATFORM_TENANT, "region": region,
                                                   "skill_id": row["skill_id"], "source": "room_auto"})

@asynccontextmanager
async def lifespan(_app):
    tasks = [asyncio.create_task(collector_loop()),
             asyncio.create_task(schedule_loop("export")),
             asyncio.create_task(schedule_loop("gold")),
             asyncio.create_task(schedule_loop("retest"))]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task


async def collector_loop() -> None:
    while True:
        try:
            await collect_once()
        except Exception:
            # Never include exception text: database/HTTP exceptions may contain
            # credentials, prompts, or matter data. Retry next cycle.
            log.warning("Training maintenance failed; will retry.")
        await asyncio.sleep(300)


def scheduled_slot(operation: str, now: datetime) -> datetime:
    """Most recent UTC boundary; a restart catches up once, never a backlog."""
    now = now.astimezone(timezone.utc)
    if operation in ("export", "gold"):
        slot = now.replace(hour=2, minute=0, second=0, microsecond=0)
        return slot if slot <= now else slot - timedelta(days=1)
    if operation != "retest":
        raise ValueError("Unknown training operation")
    slot = now.replace(hour=6, minute=0, second=0, microsecond=0)
    slot -= timedelta(days=(now.weekday() + 1) % 7)
    return slot if slot <= now else slot - timedelta(days=7)


async def scheduled_once(operation: str, now: datetime | None = None) -> None:
    slot = scheduled_slot(operation, now or datetime.now(timezone.utc))
    region = runtime().box_region()
    if region not in ("us-east", "za"):
        return
    # A separate session lock per operation covers the completion check and work
    # across workers. The existing platform audit log needs no schema change.
    lock = {"export": 871224, "retest": 871225, "gold": 871227}[operation]
    marker = encoded({"tenant_id": str(PLATFORM_TENANT), "region": region,
                      "operation": operation, "slot": slot.isoformat()})
    async with runtime().pool().acquire() as conn:
        if not await conn.fetchval("SELECT pg_try_advisory_lock($1)", lock):
            return
        try:
            if await conn.fetchval(
                """SELECT 1 FROM tank.policy_log WHERE task_type='training.schedule'
                AND action='complete' AND detail=$1::jsonb LIMIT 1""", marker,
            ):
                return
            if operation == "gold":
                await collect_room_gold(slot.date())
            elif operation == "export":
                await collect_once()
                result = await export_once(day=slot.date())
                if result["status"] != "complete":
                    return  # Missing configuration or a busy exporter can retry.
            else:
                from gold import retest
                await retest(since=slot)
            await conn.execute(
                """INSERT INTO tank.policy_log(task_type,action,by_user,detail)
                VALUES ('training.schedule','complete','tank',$1::jsonb)""", marker,
            )
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", lock)


async def schedule_loop(operation: str) -> None:
    while True:
        try:
            await scheduled_once(operation)
        except Exception:
            log.warning("Scheduled training maintenance failed; will retry.")
        await asyncio.sleep(60)


router = APIRouter(prefix="/v1/training", lifespan=lifespan)


@router.post("/tiger/{observation_id}/confirm")
async def confirm_tiger(observation_id: uuid.UUID, actor: Reviewer = Depends(require_reviewer)) -> dict[str, bool]:
    if not actor.founder:
        raise HTTPException(404, "not found")
    async with runtime().pool().acquire() as conn:
        if not await conn.fetchval("SELECT to_regclass('agent_tiger.observations')"):
            raise HTTPException(404, "not found")
        row = await conn.fetchrow(
            "SELECT * FROM agent_tiger.observations WHERE id=$1 AND tenant_id=$2", observation_id, actor.tenant,
        )
        if row is None or row["price"] is None:
            raise HTTPException(404, "not found")
        await add_candidate(conn, tenant=actor.tenant, skill="tiger.price_read", agent="tiger",
                            value={"url": row["url"], "evidence": row["evidence"]},
                            expected={"price": str(row["price"]), "currency": row["currency"],
                                      "availability": row["availability"]},
                            source="tiger_confirmed", ref=str(observation_id))
    return {"ok": True}


def exportable(row: dict[str, Any]) -> bool:
    return row["region"] in ("us-east", "za") and not row["holdout"] and bool(row["active"])


async def upload_dataset(client: httpx.AsyncClient, org: str, agent: str, day: str, rows: list[dict], region: str = "us-east") -> None:
    name = f"tervory-{agent}"
    created = await client.post("https://huggingface.co/api/repos/create",
                                json={"type": "dataset", "name": name, "organization": org, "private": True})
    if created.status_code not in (200, 201, 409):
        raise RuntimeError("Private dataset creation failed")
    repo = f"{org}/{name}"
    info = await client.get(f"https://huggingface.co/api/datasets/{repo}")
    if info.status_code != 200 or info.json().get("private") is not True:
        raise RuntimeError("Dataset is not private")
    data = "\n".join(encoded(row) for row in rows) + "\n"
    # Native Hub commit API, no new runtime dependency; a date is a complete snapshot.
    operations = [
        {"key": "header", "value": {"summary": f"Training snapshot {day}"}},
        {"key": "file", "value": {"path": f"snapshots/{region}/{day}.jsonl", "encoding": "base64",
                                  "content": base64.b64encode(data.encode()).decode()}},
    ]
    response = await client.post(f"https://huggingface.co/api/datasets/{repo}/commit/main",
                                 content="\n".join(encoded(op) for op in operations),
                                 headers={"Content-Type": "application/x-ndjson"})
    if response.status_code not in (200, 201):
        raise RuntimeError("Private dataset commit failed")


async def export_once(*, day: date | None = None) -> dict[str, Any]:
    token, org = os.environ.get("HF_TOKEN", ""), os.environ.get("HF_ORG", "")
    if not token or not org:
        return {"status": "skipped", "reason": "not configured"}
    region = runtime().box_region()
    if region not in ("us-east", "za"):
        return {"status": "skipped", "reason": "unknown region"}
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", org):
        return {"status": "skipped", "reason": "invalid organisation"}
    day = day or datetime.now(timezone.utc).date()
    exported = 0
    async with runtime().pool().acquire() as conn:
        if not await conn.fetchval("SELECT pg_try_advisory_lock(871223)"):
            return {"status": "skipped", "reason": "already running"}
        try:
            from gold import AGENTS
            async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=60,
                                         follow_redirects=False) as client:
                for agent in AGENTS:
                    done = await conn.fetchval(
                        "SELECT 1 FROM tank.training_exports WHERE region=$3 AND day=$1 AND agent=$2", day, agent, region,
                    )
                    if done:
                        continue
                    payload = []
                    scopes = await conn.fetch(
                        "SELECT DISTINCT tenant_id FROM tank.training_pairs WHERE region=$2 AND agent=$1", agent, region,
                    )
                    for scope in scopes:
                        rows = await conn.fetch(
                            """SELECT p.* FROM tank.training_pairs p
                            WHERE p.tenant_id=$1 AND p.region=$3 AND p.agent=$2 AND p.active AND NOT p.holdout
                            AND NOT EXISTS (SELECT 1 FROM tank.gold_examples g WHERE g.tenant_id=p.tenant_id
                              AND g.region=p.region AND g.input=p.input AND (g.holdout OR (g.status='rejected' AND g.id=p.gold_id)))""",
                            scope["tenant_id"], agent, region,
                        )
                        for row in rows:
                            if exportable(dict(row)):
                                # No tenant, reviewer identity or matter reference leaves the box.
                                payload.append({"region": region, "task_type": row["task_type"], "input": obj(row["input"]),
                                                "output": obj(row["output"])})
                    if not payload:
                        continue
                    await upload_dataset(client, org, agent, day.isoformat(), payload, region)
                    await conn.execute(
                        """INSERT INTO tank.training_exports(region,day,agent) VALUES ($3,$1,$2)
                        ON CONFLICT DO NOTHING""", day, agent, region,
                    )
                    exported += len(payload)
        finally:
            await conn.execute("SELECT pg_advisory_unlock(871223)")
    return {"status": "complete", "exported": exported}


@router.post("/jobs/export", dependencies=[Depends(require_job)])
async def export_job() -> dict[str, Any]:
    await collect_once()
    return await export_once()
