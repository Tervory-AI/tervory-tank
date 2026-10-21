"""Approval policy tests and real Postgres transaction/confirmation regression tests."""
from dataclasses import replace
import json
import os
from pathlib import Path
import uuid

import asyncpg
from fastapi import HTTPException
import pytest
import pytest_asyncio

import skala

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = uuid.UUID("00000000-0000-0000-0000-000000000001")


def package(tmp_path, version="1.8.0", skill="base.test", model=False):
    path = tmp_path / skill / version
    path.mkdir(parents=True, exist_ok=True)
    (path / "run.py").write_text("async def run(payload, ctx):\n    return payload\n")
    return skala.SkillPackage(skill, version, "base", 1 if model else 3,
                              "base.test" if model else None, "", {}, {}, .8, path,
                              [{"input": {"n": i}, "expected": {"ok": i != 4}, "must_refuse": i == 4} for i in range(5)])


def evaluation(pkg, passed=5):
    return {"score": passed / 5, "passed": passed, "total": 5, "details": [
        {"case_hash": skala.evidence_hash(c), "package_hash": skala.package_hash(pkg),
         "passed": i >= 5 - passed, "used_model": bool(pkg.task_type)} for i, c in enumerate(pkg.cases)]}


def reason(pkg, *, approved=None, runs=None, baseline=None):
    return skala.approval_reason(pkg, {"state": "staging", "present": True}, approved,
                                 runs if runs is not None else [evaluation(pkg)], baseline or [])


def test_older_version_and_lower_score_are_refused(tmp_path):
    old = package(tmp_path, "1.5.0")
    assert "1.5.0 is older" in reason(old, approved={"version": "1.7.0"})
    new = package(tmp_path)
    assert "below approved 100%" in reason(new, approved={"version": "1.7.0"},
                                            runs=[evaluation(new, 4)], baseline=[evaluation(new)])


def test_same_cases_and_current_source_required(tmp_path):
    pkg = package(tmp_path)
    baseline = evaluation(pkg)
    baseline["details"][0]["case_hash"] = "different"
    assert "same cases" in reason(pkg, approved={"version": "1.7.0"}, baseline=[baseline])
    old = evaluation(pkg)
    (pkg.path / "run.py").write_text("# changed source")
    assert "does not match" in reason(pkg, runs=[old])


def test_three_consecutive_complete_model_runs(tmp_path):
    pkg = package(tmp_path, model=True)
    good, bad = evaluation(pkg), evaluation(pkg, 4)
    assert "2/3 runs" in reason(pkg, runs=[good, good, bad])
    assert "0/3 runs" in reason(pkg, runs=[bad, good, good])
    assert reason(pkg, runs=[good, good, good]) is None
    assert "2/3 runs" in reason(pkg, runs=[good, good])


def test_cases_refusal_and_semver_are_required(tmp_path):
    pkg = package(tmp_path)
    assert reason(replace(pkg, cases=pkg.cases[:4]))
    assert reason(replace(pkg, version="1.8.0-rc1"))
    assert skala.version_key("1.10.0") > skala.version_key("1.9.0")
    assert skala.room_authored("base.learned.some_skill")
    assert skala.room_authored("zenas.learned.some_skill")
    assert not skala.room_authored("base.find_site")


@pytest_asyncio.fixture
async def database():
    url = os.environ.get("POOL_SCHEMA_DATABASE_URL")
    if not url:
        pytest.skip("POOL_SCHEMA_DATABASE_URL is needed for real transaction tests")
    admin = await asyncpg.connect(url)
    name = "skala_test_" + uuid.uuid4().hex
    await admin.execute(f'CREATE DATABASE "{name}"')
    from urllib.parse import urlsplit, urlunsplit
    split = urlsplit(url)
    isolated = urlunsplit((split.scheme, split.netloc, "/" + name, split.query, split.fragment))
    db = await asyncpg.create_pool(isolated, min_size=1, max_size=4)
    try:
        async with db.acquire() as conn:
            schema = (ROOT / "tank/schema.sql").read_text()
            await conn.execute(schema)
            await conn.execute(schema)  # Additive, repeatable on an empty database.
        yield db
    finally:
        await db.close()
        await admin.execute(f'DROP DATABASE "{name}"')
        await admin.close()


async def seed(db, pkg, state="staging", *, once_approved=False, runs=1, passed=5):
    async with db.acquire() as conn:
        await conn.execute("""INSERT INTO tank.skills (id,version,agent,state,approved_at)
            VALUES ($1,$2,'base',$3,CASE WHEN $4 THEN now() ELSE NULL END)""",
            pkg.id, pkg.version, state, once_approved)
        for _ in range(runs):
            data = evaluation(pkg, passed)
            await conn.execute("""INSERT INTO tank.skill_evals (skill_id,version,score,passed,total,details)
                VALUES ($1,$2,$3,$4,5,$5::jsonb)""", pkg.id, pkg.version, data["score"], passed, json.dumps(data["details"]))


async def states(db, skill="base.test"):
    async with db.acquire() as conn:
        return {r["version"]: r["state"] for r in await conn.fetch("SELECT version,state FROM tank.skills WHERE id=$1", skill)}


@pytest.mark.asyncio
async def test_forward_approval_retires_older_candidates_only(database, tmp_path):
    pkgs = [package(tmp_path, v) for v in ["1.5.0", "1.6.0", "1.7.0", "1.8.0", "1.9.0"]]
    for pkg, state in zip(pkgs, ["candidate", "staging", "approved", "staging", "candidate"]):
        await seed(database, pkg, state, once_approved=state == "approved")
    with pytest.raises(HTTPException, match="1.5.0 is older"):
        await skala.change_version(database, pkgs[0], "founder", "approve", region="us-east")
    await skala.change_version(database, pkgs[3], "founder", "approve", region="us-east")
    assert await states(database) == {"1.5.0": "retired", "1.6.0": "retired", "1.7.0": "retired", "1.8.0": "approved", "1.9.0": "candidate"}


@pytest.mark.asyncio
async def test_retirement_and_confirmed_rollback(database, tmp_path):
    old, current, pending = [package(tmp_path, v) for v in ["1.6.0", "1.7.0", "1.8.0"]]
    await seed(database, old, "retired", once_approved=True)
    await seed(database, current, "approved", once_approved=True)
    await seed(database, pending)
    await skala.change_version(database, pending, "founder", "retire", region="us-east")
    assert (await states(database))[current.version] == "approved"
    for pkg, action, confirm in [(current, "retire", False), (old, "rollback", False), (pending, "rollback", True)]:
        with pytest.raises(HTTPException):
            await skala.change_version(database, pkg, "founder", action, region="us-east", confirmed=confirm)
    await skala.change_version(database, old, "founder", "rollback", region="us-east", confirmed=True)
    assert (await states(database))[old.version] == "approved"
    async with database.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM tank.skill_approvals WHERE tenant_id=$1 AND action='rollback'", PLATFORM)
        assert row["acted_by"] == "founder" and row["acted_at"]
        assert row["previous_version"] == current.version


@pytest.mark.asyncio
async def test_bulk_confirms_exact_snapshot_and_excludes_room_code(database, tmp_path):
    pkgs = [package(tmp_path, skill=s) for s in ["base.one", "base.two", "base.learned.test"]]
    for pkg in pkgs:
        await seed(database, pkg)
    packages = {(p.id, p.version): p for p in pkgs}
    preview = await skala.bulk_preview(database, packages, "founder", region="us-east")
    assert {i["id"] for i in preview["items"]} == {"base.one", "base.two"}
    late = package(tmp_path, skill="base.late")
    await seed(database, late)
    packages[(late.id, late.version)] = late
    for actor, confirmed in [("founder", False), ("other", True)]:
        with pytest.raises(HTTPException):
            await skala.bulk_confirm(database, packages, actor, preview["token"], confirmed, region="us-east")
    result = await skala.bulk_confirm(database, packages, "founder", preview["token"], True, region="us-east")
    assert {i["id"] for i in result["approved"]} == {"base.one", "base.two"}
    assert (await states(database, late.id))[late.version] == "staging"
    assert (await states(database, pkgs[2].id))[pkgs[2].version] == "staging"
    with pytest.raises(HTTPException):
        await skala.bulk_confirm(database, packages, "founder", preview["token"], True, region="us-east")
    async with database.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM tank.skill_approvals WHERE tenant_id=$1", PLATFORM) == 2


@pytest.mark.asyncio
async def test_bulk_stale_evidence_is_atomic(database, tmp_path):
    pkgs = [package(tmp_path, skill=s) for s in ["base.a", "base.b"]]
    for pkg in pkgs:
        await seed(database, pkg)
    packages = {(p.id, p.version): p for p in pkgs}
    preview = await skala.bulk_preview(database, packages, "founder", region="us-east")
    async with database.acquire() as conn:
        await conn.execute("UPDATE tank.skill_evals SET score=.5 WHERE skill_id=$1", pkgs[1].id)
    with pytest.raises(HTTPException):
        await skala.bulk_confirm(database, packages, "founder", preview["token"], True, region="us-east")
    for pkg in pkgs:
        assert (await states(database, pkg.id))[pkg.version] == "staging"
    async with database.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM tank.skill_approvals WHERE tenant_id=$1", PLATFORM) == 0


@pytest.mark.asyncio
async def test_model_two_runs_stays_staging_and_learned_needs_source(database, tmp_path):
    model = package(tmp_path, model=True)
    await seed(database, model, runs=2)
    with pytest.raises(HTTPException, match="2/3 runs"):
        await skala.change_version(database, model, "founder", "approve", region="us-east")
    assert (await states(database))[model.version] == "staging"
    learned = package(tmp_path, skill="base.learned.example")
    await seed(database, learned)
    with pytest.raises(HTTPException, match="full run.py"):
        await skala.change_version(database, learned, "founder", "approve", region="us-east")
    review = await skala.source_review(database, learned, "founder")
    assert review["source"] == (learned.path / "run.py").read_text()
    with pytest.raises(HTTPException):
        await skala.change_version(database, learned, "other", "approve", region="us-east", confirmed=True, review_token=review["review_token"])
    await skala.change_version(database, learned, "founder", "approve", region="us-east", confirmed=True, review_token=review["review_token"])


@pytest.mark.asyncio
async def test_concurrent_approvals_cannot_move_backwards(database, tmp_path):
    import asyncio
    current, newer, newest = [package(tmp_path, v) for v in ["1.7.0", "1.8.0", "1.9.0"]]
    for pkg in [current, newer, newest]:
        await seed(database, pkg, "approved" if pkg is current else "staging", once_approved=pkg is current)
    results = await asyncio.gather(*[
        skala.change_version(database, pkg, "founder", "approve", region="us-east")
        for pkg in [newest, newer]], return_exceptions=True)
    assert any(isinstance(r, dict) for r in results)
    final = await states(database)
    assert final[newest.version] == "approved"
    assert sum(state == "approved" for state in final.values()) == 1


@pytest.mark.asyncio
async def test_zenas_gate_blocks_bulk_and_individual(database, tmp_path, monkeypatch):
    pkg = package(tmp_path, skill="zenas.example")
    await seed(database, pkg)
    async def blocked(conn, skill_id, *, region):
        assert skill_id == pkg.id and region == "za"
        return "The made-up-case test has not passed on this box."
    monkeypatch.setattr(skala, "zenas_approval_refusal", blocked)
    with pytest.raises(HTTPException, match="made-up-case"):
        await skala.change_version(database, pkg, "founder", "approve", region="za")
    preview = await skala.bulk_preview(database, {(pkg.id, pkg.version): pkg}, "founder", region="za")
    assert preview["items"] == []
