"""Real SQL/ASGI checks for founder onboarding and tenant-owned Workspace state."""

import uuid
import asyncio
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from test_tank_tenant_boundaries import boundary as _boundary
from test_tank_ladder import ladder as _ladder

boundary = _boundary
ladder = _ladder


def headers(b, tenant, founder=False):
    import trigger_signin_config as registry
    # Declare each disposable fixture organisation, then sign its real claims.
    bindings = registry.config("us-east")["organisations"]
    if str(tenant) not in bindings.values():
        bindings[str(tenant.int % (10 ** 25))] = str(tenant)
    return b.native_headers("founder-fixture" if founder else "member-fixture",
                            "org_admin" if founder else "member", tenant)


@pytest.mark.asyncio
async def test_founder_home_onboarding_is_immutable_and_ordinary_requests_use_it(
    boundary,
):
    b = boundary
    tenant = uuid.uuid4()
    path = f"/v1/tenants/{tenant}/home"
    assert (
        await b.client.put(path, json={"home_region": "za"}, headers=headers(b, tenant))
    ).status_code == 403
    assert (await b.client.get(path)).status_code == 404
    response = await b.client.put(
        path, json={"home_region": "za"}, headers=headers(b, tenant, True)
    )
    assert response.status_code == 200 and response.json()["home_region"] == "za"
    assert (
        await b.client.put(
            path, json={"home_region": "za"}, headers=headers(b, tenant, True)
        )
    ).status_code == 200
    assert (
        await b.client.put(
            path, json={"home_region": "us-east"}, headers=headers(b, tenant, True)
        )
    ).status_code == 409
    assert (
        await b.client.put(
            path, json={"home_region": "invalid"}, headers=headers(b, tenant, True)
        )
    ).status_code == 422
    assert (await b.client.get(path)).json() == {
        "tenant_id": str(tenant),
        "home_region": "za",
    }
    from tenant_regions import resolve_home

    assert await resolve_home(b.tank, tenant, None) == "za"
    with pytest.raises(HTTPException) as error:
        await resolve_home(b.tank, tenant, "us-east")
    assert error.value.status_code == 409
    result = await b.client.post(
        "/v1/route",
        json={
            "tenant_id": str(tenant),
            "messages": [{"role": "user", "content": "placeholder"}],
        },
    )
    assert result.status_code == 403  # US Tank cannot dispatch this ZA tenant.
    assert not b.calls
    assert (
        await b.client.put(
            f"/v1/tenants/{b.tenants[0]}/home",
            json={"home_region": "za"},
            headers=headers(b, b.tenants[0], True),
        )
    ).status_code == 409
    request = {
        "tenant_id": str(tenant),
        "messages": [{"role": "user", "content": "placeholder"}],
    }
    assert (
        await b.client.post(
            "/v1/route/batch", json={"id": str(uuid.uuid4()), "requests": [request]}
        )
    ).status_code == 403
    assert (
        await b.client.post("/v1/tasks", json={**request, "title": "placeholder"})
    ).status_code == 403


async def seed(b, tenant, *, outcome="delivered", status="done"):
    ledger, task = uuid.uuid4(), uuid.uuid4()
    async with b.pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,rung,outcome)
            VALUES($1,$2,'base','placeholder.task','placeholder',1,$3)""",
            ledger,
            tenant,
            outcome,
        )
        await conn.execute(
            """INSERT INTO tank.tasks(id,tenant_id,created_by,agent,task_type,title,input,status,result,ledger_id)
            VALUES($1,$2,'fixture','base','placeholder.task','placeholder task','[]'::jsonb,$3,'placeholder result',$4)""",
            task,
            tenant,
            status,
            ledger,
        )
    return task, ledger


@pytest.mark.asyncio
async def test_board_states_results_and_feedback_are_tenant_bound(boundary):
    b = boundary
    own, ledger = await seed(b, b.tenants[0])
    unknown, _ = await seed(b, b.tenants[0], outcome="unverified")
    foreign, _ = await seed(b, b.tenants[1])
    actor = headers(b, b.tenants[0])
    response = await b.client.get("/v1/workspace/tasks", headers=actor)
    assert response.status_code == 200
    rows = {row["id"]: row for row in response.json()["tasks"]}
    assert rows[str(own)]["status"] == "delivered"
    assert rows[str(unknown)]["status"] == "unverified"
    assert str(foreign) not in rows
    results = (await b.client.get("/v1/workspace/results", headers=actor)).json()[
        "results"
    ]
    assert len(results) == 2 and all("download_url" not in row for row in results)
    response = await b.client.post(
        f"/v1/workspace/tasks/{own}/feedback",
        json={"verdict": "wrong", "note": "placeholder correction"},
        headers=actor,
    )
    assert response.status_code == 200 and response.json()["verdict"] == "wrong"
    async with b.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT feedback,feedback_kind,feedback_note,feedback_by FROM tank.ledger WHERE id=$1 AND tenant_id=$2",
            ledger,
            b.tenants[0],
        )
        assert dict(row) == {
            "feedback": "rejected",
            "feedback_kind": "wrong",
            "feedback_note": "placeholder correction",
            "feedback_by": "member-fixture",
        }
    assert (
        await b.client.post(
            f"/v1/workspace/tasks/{foreign}/feedback",
            json={"verdict": "wrong"},
            headers=actor,
        )
    ).status_code == 404
    assert (
        await b.client.post(
            f"/v1/workspace/tasks/{unknown}/feedback",
            json={"verdict": "wrong"},
            headers=actor,
        )
    ).status_code == 409
    assert (
        await b.client.post(
            f"/v1/workspace/tasks/{own}/feedback",
            json={"verdict": "wrong", "by": "spoofed"},
            headers=actor,
        )
    ).status_code == 422
    assert (
        await b.client.post(
            f"/v1/workspace/tasks/{own}/feedback",
            json={"verdict": "wrong", "note": "x" * 1001},
            headers=actor,
        )
    ).status_code == 422
    assert (
        await b.client.get("/v1/workspace/tasks?limit=201", headers=actor)
    ).status_code == 422


@pytest.mark.asyncio
async def test_queued_task_remains_queued_then_receipt_delivers_it(ladder, monkeypatch):
    import priority_queue
    from test_tank_priority_offpeak import prepare

    b = ladder
    clock, _ = await prepare(b, monkeypatch)
    async with b.pool.acquire() as conn:
        await conn.execute(
            "UPDATE tank.policy SET priority='offpeak' WHERE tenant_id=$1 AND task_type='base.normalize'",
            b.tenants[0],
        )
    monkeypatch.setattr(priority_queue, "kick", Mock())
    task = await b.tank.create_task(
        b.tank.TaskCreate(
            tenant_id=b.tenants[0],
            title="Offline task",
            agent="base",
            task_type="base.normalize",
            messages=[b.tank.Message(role="user", content="Offline request")],
        )
    )
    await asyncio.gather(*tuple(b.tank._background))
    actor = headers(b, b.tenants[0])
    rows = (await b.client.get("/v1/workspace/tasks", headers=actor)).json()["tasks"]
    row = next(row for row in rows if row["id"] == str(task["id"]))
    assert row["status"] == "queued" and row["error"] is None and not b.sent
    clock[0] = clock[0].replace(hour=4)
    await priority_queue.process_once(b.tank)
    rows = (await b.client.get("/v1/workspace/tasks", headers=actor)).json()["tasks"]
    row = next(row for row in rows if row["id"] == str(task["id"]))
    assert row["status"] == "delivered" and "Offline answer" in row["result"]
    assert (
        row["cost_usd"] is not None
        and row["cost_pending"] is False
        and len(b.sent) == 1
    )


@pytest.mark.asyncio
async def test_existing_conversation_prevents_reassignment_and_wrong_box_actor_is_refused(
    boundary,
):
    b = boundary
    owner = uuid.uuid4()
    async with b.pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO tank.command_threads(tenant_id,user_id,title,state)
            VALUES($1,'fixture','private conversation','{}')""",
            owner,
        )
    path = f"/v1/tenants/{owner}/home"
    assert (
        await b.client.put(
            path, json={"home_region": "za"}, headers=headers(b, b.tenants[0], True)
        )
    ).status_code == 409
    new = uuid.uuid4()
    assert (
        await b.client.put(
            f"/v1/tenants/{new}/home",
            json={"home_region": "za"},
            headers=headers(b, b.tenants[0], True),
        )
    ).status_code == 200
    assert (
        await b.client.get("/v1/command/tools", headers=headers(b, new))
    ).status_code == 403


def test_workspace_routes_private_content_only_to_the_recorded_home():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", "tests/platform_region_contract.cjs"],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
