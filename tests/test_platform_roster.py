"""Roster changes use the real Skala eval handler; only model transport is stubbed."""

import json
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi import HTTPException

import roster_validation
import skala_revalidation
from gold import PLATFORM_TENANT
from skala_b3_b4.test_lifecycle import env as _skala_env, package, policy, seed, jobs

env = _skala_env


ROWS = [
    {
        "model_name": "luna",
        "litellm_params": {
            "model": "fixture/luna",
            "api_base": "https://fixture.invalid",
        },
        "model_info": {
            "host": "fixture",
            "id": "generated-first",
            "input_cost_per_token": 1,
        },
    }
]


def test_fingerprint_tracks_deployments_but_not_prices_ids_order_or_keys():
    updated = [
        {
            "model_name": "luna",
            "litellm_params": {
                "model": "fixture/luna",
                "api_base": "https://fixture.invalid",
                "api_key": "placeholder",
            },
            "model_info": {
                "host": "fixture",
                "id": "generated-second",
                "input_cost_per_token": 2,
            },
        }
    ]
    assert roster_validation.fingerprint(ROWS) == roster_validation.fingerprint(updated)
    assert roster_validation.fingerprint(
        ROWS + updated
    ) != roster_validation.fingerprint(ROWS)
    assert roster_validation.fingerprint(
        ROWS + updated
    ) == roster_validation.fingerprint(updated + ROWS)
    for rows in ([], [{}]):
        with pytest.raises(ValueError):
            roster_validation.fingerprint(rows)


async def baseline(e, monkeypatch):
    await e.db.execute(
        "DELETE FROM tank.roster_observations WHERE tenant_id=$1", PLATFORM_TENANT
    )
    response = httpx.Response(
        200,
        json={"data": ROWS},
        request=httpx.Request("GET", "https://fixture.invalid/model/info"),
    )
    http = SimpleNamespace(get=AsyncMock(return_value=response))
    monkeypatch.setattr(e.tank, "_http", http)
    assert await roster_validation.observe(e.tank) == 0
    return http


def changed(http):
    http.get.return_value = httpx.Response(
        200,
        json={
            "data": ROWS
            + [
                {
                    "model_name": "sol",
                    "litellm_params": {"model": "fixture/sol"},
                    "model_info": {"host": "fixture"},
                }
            ]
        },
        request=httpx.Request("GET", "https://fixture.invalid/model/info"),
    )


@pytest.mark.asyncio
async def test_changed_roster_reruns_every_approved_package_and_records_validation(
    env, tmp_path, monkeypatch
):
    e = env
    await policy(e)
    for name, task, state in (
        ("base.first", "test.b3.write", "approved"),
        ("base.other", "test.b3.other", "approved"),
        ("base.pending", "test.b3.write", "candidate"),
    ):
        if task == "test.b3.other":
            await policy(e, task=task)
        await seed(e, package(tmp_path, name=name, task=task), state)
    http = await baseline(e, monkeypatch)
    assert await roster_validation.observe(e.tank) == 0
    changed(http)
    assert await roster_validation.observe(e.tank) == 2
    assert await roster_validation.observe(e.tank) == 0
    assert {r["skill_id"] for r in await jobs(e)} == {"base.first", "base.other"}
    assert await skala_revalidation.drain(e.tank) == 2
    assert len(e.calls) == 8 and {c[0] for c in e.calls} == {"luna"}
    for row in await jobs(e):
        skill = await e.db.fetchrow(
            "SELECT state,models_validated FROM tank.skills WHERE id=$1 AND version=$2",
            row["skill_id"],
            row["version"],
        )
        validation = json.loads(skill["models_validated"])[0]
        assert (
            validation["validated"] is True
            and len(validation["roster_fingerprint"]) == 64
        )
        assert skill["state"] == "approved"
    assert (
        await e.db.fetchval(
            "SELECT count(*) FROM tank.skill_approvals WHERE tenant_id=$1",
            PLATFORM_TENANT,
        )
        == 0
    )


@pytest.mark.asyncio
async def test_failed_roster_eval_retains_serving_policy_and_rollback_package(
    env, tmp_path, monkeypatch
):
    e = env
    await policy(e, model="astra")
    pkg = package(tmp_path)
    await seed(e, pkg)
    http = await baseline(e, monkeypatch)
    changed(http)
    assert await roster_validation.observe(e.tank) == 1
    assert await skala_revalidation.drain(e.tank) == 1
    row = await e.db.fetchrow(
        "SELECT state,models_validated,approved_at FROM tank.skills WHERE id=$1 AND version=$2",
        pkg.id,
        pkg.version,
    )
    assert (
        row["state"] == "approved"
        and row["approved_at"] is not None
        and pkg.path.is_dir()
    )
    assert json.loads(row["models_validated"])[0]["validated"] is False
    assert (
        await e.db.fetchval(
            "SELECT model FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL",
            pkg.task_type,
        )
        == "astra"
    )


@pytest.mark.asyncio
async def test_missing_policy_fails_before_any_model_call(env, tmp_path, monkeypatch):
    e = env
    await seed(e, package(tmp_path, task="test.b3.unrouted"))
    http = await baseline(e, monkeypatch)
    changed(http)
    assert await roster_validation.observe(e.tank) == 1
    assert await skala_revalidation.drain(e.tank) == 1 and e.calls == []
    assert (await jobs(e))[0]["error"] == "eval_gate_failed"


@pytest.mark.asyncio
async def test_code_only_approval_is_evaluated_without_a_model(
    env, tmp_path, monkeypatch
):
    e = env
    pkg = package(tmp_path, name="base.code", task=None, code=True)
    (pkg.path / "run.py").write_text(
        'async def run(payload, ctx):\n    return {"text": "good"} if payload.get("text") else {"refused": True}\n'
    )
    await seed(e, pkg)
    http = await baseline(e, monkeypatch)
    changed(http)
    assert await roster_validation.observe(e.tank) == 1
    assert await skala_revalidation.drain(e.tank) == 1 and e.calls == []
    row = await e.db.fetchrow(
        "SELECT state,models_validated FROM tank.skills WHERE id=$1 AND version=$2",
        pkg.id,
        pkg.version,
    )
    assert (
        row["state"] == "approved"
        and json.loads(row["models_validated"])[0]["validated"] is True
    )


@pytest.mark.asyncio
async def test_roster_revalidates_current_tenant_policy_overrides_too(
    env, tmp_path, monkeypatch
):
    from skala_b3_b4.test_lifecycle import TENANT

    e = env
    await policy(e)
    await policy(e, model="sol", tenant=TENANT)
    await seed(e, package(tmp_path))
    http = await baseline(e, monkeypatch)
    changed(http)
    assert await roster_validation.observe(e.tank) == 2
    assert await skala_revalidation.drain(e.tank) == 2
    assert {c[0] for c in e.calls} == {"luna", "sol"} and len(e.calls) == 8
    records = await jobs(e)
    assert {r["policy_tenant_id"] for r in records} == {None, TENANT}


@pytest.mark.asyncio
async def test_private_package_cases_use_only_owners_policy_permissions(
    env, tmp_path, monkeypatch
):
    import uuid
    from skala_b3_b4.test_lifecycle import TENANT

    e = env
    await policy(e)
    await policy(e, model="astra", tenant=uuid.uuid4())
    pkg = package(tmp_path, name="base.private")
    await seed(e, pkg)
    await e.db.execute(
        """INSERT INTO tank.agent_skill_submissions
        (skill_id,version,tenant_id,region,submitted_by_room,package,sha256)
        VALUES($1,$2,$3,$4,'base','{}','fixture')""",
        pkg.id,
        pkg.version,
        TENANT,
        e.tank.box_region(),
    )
    http = await baseline(e, monkeypatch)
    changed(http)
    assert await roster_validation.observe(e.tank) == 1
    assert await skala_revalidation.drain(e.tank) == 1
    assert {c[0] for c in e.calls} == {"luna"} and len(e.calls) == 4
    assert (await jobs(e))[0]["policy_tenant_id"] == TENANT


@pytest.mark.asyncio
@pytest.mark.parametrize("unavailable", [False, True])
async def test_installed_worker_observes_roster_and_still_drains_on_metadata_failure(
    monkeypatch, caplog, unavailable
):
    ready = asyncio.Event()
    observer = AsyncMock(
        return_value=0,
        side_effect=RuntimeError("private upstream detail") if unavailable else None,
    )

    async def drain(_):
        ready.set()
        return 0

    monkeypatch.setattr(roster_validation, "observe", observer)
    monkeypatch.setattr(skala_revalidation, "drain", drain)
    app = FastAPI()
    tank = SimpleNamespace()
    skala_revalidation.install(app, tank)
    await app.router.on_startup[0]()
    try:
        await asyncio.wait_for(ready.wait(), 30)
    finally:
        await app.router.on_shutdown[0]()
    observer.assert_awaited_once_with(tank)
    assert "private upstream detail" not in caplog.text


@pytest.mark.asyncio
async def test_roster_evals_precede_new_policy_and_existing_target_gate_still_holds(
    env, tmp_path, monkeypatch
):
    from skala_b3_b4.test_lifecycle import TASK

    e = env
    await policy(e)
    await policy(e, task="test.b3.other")
    await seed(e, package(tmp_path, name="base.first"))
    await seed(e, package(tmp_path, name="base.other", task="test.b3.other"))
    http = await baseline(e, monkeypatch)
    changed(http)
    with pytest.raises(HTTPException) as pending:
        await policy(e, model="sol")
    assert pending.value.status_code == 409 and not e.calls
    assert len(await jobs(e)) == 2
    assert (
        await e.db.fetchval(
            "SELECT model FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL",
            TASK,
        )
        == "luna"
    )
    assert await skala_revalidation.drain(e.tank) == 2
    await policy(e, model="sol")
    assert (
        await e.db.fetchval(
            "SELECT model FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL",
            TASK,
        )
        == "luna"
    )
    assert await skala_revalidation.drain(e.tank) == 1
    assert (
        await e.db.fetchval(
            "SELECT model FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL",
            TASK,
        )
        == "sol"
    )


@pytest.mark.asyncio
async def test_known_roster_metadata_outage_refuses_a_policy_write_without_spending(
    env, monkeypatch
):
    e = env
    await policy(e)
    http = await baseline(e, monkeypatch)
    http.get.side_effect = httpx.ConnectError("private connection detail")
    with pytest.raises(HTTPException) as unavailable:
        await policy(e, model="sol")
    assert unavailable.value.status_code == 503 and not e.calls
    assert "private" not in unavailable.value.detail


@pytest.mark.asyncio
async def test_already_held_proposal_waits_for_all_roster_evals_and_rechecks_its_target(
    env, tmp_path, monkeypatch
):
    from skala_b3_b4.test_lifecycle import TASK

    e = env
    await policy(e)
    await policy(e, task="test.b3.other")
    await seed(e, package(tmp_path, name="base.first"))
    await seed(e, package(tmp_path, name="base.other", task="test.b3.other"))
    await policy(e, model="sol")
    http = await baseline(e, monkeypatch)
    changed(http)
    assert await roster_validation.observe(e.tank) == 3
    assert await skala_revalidation.drain(e.tank, limit=1) == 1
    assert (
        await e.db.fetchval(
            "SELECT model FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL",
            TASK,
        )
        == "luna"
    )
    assert await skala_revalidation.drain(e.tank) == 3
    assert (
        await e.db.fetchval(
            "SELECT model FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL",
            TASK,
        )
        == "sol"
    )
    row = await e.db.fetchrow(
        "SELECT models_validated FROM tank.skills WHERE id='base.first'"
    )
    validated = json.loads(row["models_validated"])
    assert any(
        v["model"] == "sol" and v.get("roster_fingerprint") and v["validated"]
        for v in validated
    )
    assert len(e.calls) == 16
