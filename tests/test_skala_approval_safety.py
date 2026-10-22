"""Approval policy tests and real Postgres transaction/confirmation regression tests."""
from dataclasses import replace
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import uuid

import asyncpg
from fastapi import HTTPException
import pytest
import pytest_asyncio

import skala

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = skala.PLATFORM_TENANT


def package(tmp_path, version="1.8.0", skill="base.test", model=False):
    path = tmp_path / skill / version
    path.mkdir(parents=True, exist_ok=True)
    (path / "run.py").write_text("async def run(payload, ctx):\n    return payload\n")
    return skala.SkillPackage(skill, version, "base", 1 if model else 3,
                              "base.test" if model else None, "", {}, {}, .8, path,
                              [{"input": {"n": i}, "expected": {"ok": i != 4}, "must_refuse": i == 4} for i in range(5)])


def evaluation(pkg, passed=None):
    total = len(pkg.cases)
    passed = total if passed is None else passed
    return {"score": passed / total, "passed": passed, "total": total, "details": [
        {"case_hash": skala.evidence_hash(c), "package_hash": skala.package_hash(pkg),
         "passed": i >= total - passed, "used_model": bool(pkg.task_type)} for i, c in enumerate(pkg.cases)]}


def reason(pkg, *, approved=None, runs=None, baseline=None):
    return skala.approval_reason(pkg, {"state": "staging", "present": True}, approved,
                                 runs if runs is not None else [evaluation(pkg)], baseline or [])


@pytest.mark.asyncio
async def test_mutating_skill_cannot_change_eval_cases_or_package_hash(tmp_path):
    pkg = package(tmp_path)
    (pkg.path / "run.py").write_text(
        "async def run(payload, ctx):\n"
        "    payload['nested']['values'].append('changed')\n"
        "    payload['ok'] = True\n"
        "    return payload\n")
    pkg.cases = [{"input": {"nested": {"values": ["original"]}}, "expected": {"ok": True}}]
    original_cases = copy.deepcopy(pkg.cases)
    original_hash = skala.package_hash(pkg)
    for _ in range(2):
        result = await skala.run_evals(pkg, lambda: SimpleNamespace(cost_usd=0))
        assert result["passed"] == 1
        detail = result["details"][0]
        assert detail["result"]["nested"]["values"] == ["original", "changed"]
        assert detail["result"]["_skill"] == pkg.ref
        assert "_ms" in detail["result"]
        assert pkg.cases == original_cases
        assert skala.package_hash(pkg) == original_hash
        assert detail["case_hash"] == skala.evidence_hash(original_cases[0])
        assert detail["package_hash"] == original_hash


def test_older_version_and_lower_score_are_refused(tmp_path):
    old = package(tmp_path, "1.5.0")
    assert "1.5.0 is older" in reason(old, approved={"version": "1.7.0"})
    new = package(tmp_path)
    assert "below approved 100.0%" in reason(new, approved={"version": "1.7.0"},
                                            runs=[evaluation(new, 4)], baseline=[evaluation(new)])


def test_same_cases_and_current_source_required(tmp_path):
    pkg = package(tmp_path)
    baseline = evaluation(pkg)
    baseline["details"][0]["case_hash"] = "different"
    assert "drops or changes 1 of approved 1.7.0's cases" in reason(pkg, approved={"version": "1.7.0"}, baseline=[baseline])
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


async def seed(db, pkg, state="staging", *, once_approved=False, runs=1, passed=None):
    async with db.acquire() as conn:
        await conn.execute("""INSERT INTO tank.skills (id,version,agent,state,approved_at)
            VALUES ($1,$2,'base',$3,CASE WHEN $4 THEN now() ELSE NULL END)""",
            pkg.id, pkg.version, state, once_approved)
        for _ in range(runs):
            data = evaluation(pkg, passed)
            await conn.execute("""INSERT INTO tank.skill_evals (skill_id,version,score,passed,total,details)
                VALUES ($1,$2,$3,$4,$5,$6::jsonb)""", pkg.id, pkg.version, data["score"], data["passed"], data["total"], json.dumps(data["details"]))


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
    with pytest.raises(HTTPException, match="every Python file"):
        await skala.change_version(database, learned, "founder", "approve", region="us-east")
    review = await skala.source_review(database, learned, "founder")
    assert review["source"] == (learned.path / "run.py").read_text()
    assert review["files"] == [{"path": "run.py", "source": review["source"]}]
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


def test_founder_api_confirmation_and_origin_checks():
    import subprocess
    result = subprocess.run(["node", str(ROOT / "tests/skala_api.cjs")], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.asyncio
async def test_missing_zenas_tables_refuse_without_hiding_other_skills(database, tmp_path):
    pkg = package(tmp_path, skill="zenas.example")
    await seed(database, pkg)
    async with database.acquire() as conn:
        evidence = await skala.review_evidence(conn, pkg, region="za")
    assert "unavailable on this box" in evidence["reason"]


@pytest.mark.asyncio
@pytest.mark.parametrize("bulk", [False, True])
async def test_superset_version_is_approved(database, tmp_path, bulk):
    old = package(tmp_path, "1.7.0")
    old.cases = old.cases[:3]
    new = package(tmp_path)
    await seed(database, old, "approved", once_approved=True)
    await seed(database, new)
    if bulk:
        packages = {(p.id, p.version): p for p in [old, new]}
        preview = await skala.bulk_preview(database, packages, "founder", region="us-east")
        assert [(r["version"], r["score"]) for r in preview["items"]] == [(new.version, 1)]
        await skala.bulk_confirm(database, packages, "founder", preview["token"], True, region="us-east")
    else:
        await skala.change_version(database, new, "founder", "approve", region="us-east")
    assert await states(database) == {old.version: "retired", new.version: "approved"}


@pytest.mark.asyncio
@pytest.mark.parametrize("edit", [False, True])
async def test_version_dropping_or_editing_an_approved_case_is_refused(database, tmp_path, edit):
    old = package(tmp_path, "1.7.0")
    new = package(tmp_path)
    if edit:
        new.cases[0] = {**new.cases[0], "expected": {"changed": True}}
    else:
        new.cases = new.cases[1:] + [{"input": {"n": 5}, "expected": {"ok": True}}]
    await seed(database, old, "approved", once_approved=True)
    await seed(database, new)
    with pytest.raises(HTTPException) as refused:
        await skala.change_version(database, new, "founder", "approve", region="us-east")
    assert refused.value.status_code == 409
    assert refused.value.detail == "1.8.0 drops or changes 1 of approved 1.7.0's cases"
    preview = await skala.bulk_preview(database, {(p.id, p.version): p for p in [old, new]}, "founder", region="us-east")
    assert preview["items"] == []
    assert (await states(database))[old.version] == "approved"


def test_extra_passing_cases_cannot_hide_a_regression(tmp_path):
    old = package(tmp_path, "1.7.0")
    new = package(tmp_path)
    new.cases += [{"input": {"n": n}, "expected": {"ok": True}} for n in range(5, 10)]
    # Both aggregate scores are 80%, but the candidate scores 60% on the old cases.
    assert reason(new, approved={"version": old.version}, runs=[evaluation(new, 8)],
                  baseline=[evaluation(old, 4)]) == "scores 60.0%, below approved 80.0%."


def test_added_case_failures_use_own_gate_without_lowering_baseline_score(tmp_path):
    old = package(tmp_path, "1.7.0")
    old.cases = old.cases[:3]
    new = package(tmp_path)
    latest = evaluation(new)
    latest["details"][3]["passed"] = False
    latest.update(score=.8, passed=4)
    assert reason(new, approved={"version": old.version}, runs=[latest], baseline=[evaluation(old)]) is None


@pytest.mark.parametrize("missing", ["all", "one", "run"])
def test_legacy_approved_evidence_requests_an_approved_eval(tmp_path, missing):
    pkg = package(tmp_path)
    baseline = [evaluation(pkg)]
    if missing == "run":
        baseline = []
    else:
        for d in baseline[0]["details"][:1 if missing == "one" else None]:
            d.pop("case_hash")
    assert reason(pkg, approved={"version": "1.7.0"}, baseline=baseline) == "Run evals on approved 1.7.0 first"


def test_regression_percentage_has_one_decimal(tmp_path):
    pkg = package(tmp_path)
    pkg.cases += [{"input": {"n": n}, "expected": {"ok": True}} for n in range(5, 11)]
    assert reason(pkg, approved={"version": "1.7.0"}, runs=[evaluation(pkg, 9)],
                  baseline=[evaluation(pkg)]) == "scores 81.8%, below approved 100.0%."


@pytest.mark.asyncio
@pytest.mark.parametrize("pending_state", ["candidate", "staging"])
async def test_retire_route_handles_missing_package(database, tmp_path, monkeypatch, pending_state):
    import secrets
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("TANK_API_KEY", secrets.token_urlsafe(24))
    monkeypatch.setenv("LITELLM_MASTER_KEY", secrets.token_urlsafe(24))
    import main
    current, absent = package(tmp_path, "1.7.0"), package(tmp_path)
    await seed(database, current, "approved", once_approved=True)
    await seed(database, absent, pending_state)
    async with database.acquire() as conn:
        await conn.execute("UPDATE tank.skills SET present=false WHERE id=$1 AND version=$2", absent.id, absent.version)
    monkeypatch.setattr(main, "pool", lambda: database)
    monkeypatch.setattr(main, "_packages", {})
    result = await main.retire_skill(absent.id, absent.version, main.Approval(by="founder"))
    assert result["state"] == "retired"
    assert (await states(database))[current.version] == "approved"
    async with database.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM tank.skill_approvals WHERE tenant_id=$1 AND action='retire'", PLATFORM)
        assert row["skill_id"] == absent.id and row["version"] == absent.version and row["acted_by"] == "founder"


@pytest.mark.asyncio
async def test_review_hashes_and_returns_every_python_file_and_consumes_token(database, tmp_path):
    pkg = package(tmp_path, skill="base.learned.example")
    helper = pkg.path / "nested" / "helper.py"
    helper.parent.mkdir()
    helper.write_text("VALUE = 1\n")
    (pkg.path / "README.md").write_text("Documentation only.")
    await seed(database, pkg)
    review = await skala.source_review(database, pkg, "founder")
    assert {f["path"]: f["source"] for f in review["files"]} == {
        "run.py": (pkg.path / "run.py").read_text(), "nested/helper.py": "VALUE = 1\n"}
    original_hash = skala.package_hash(pkg)
    for mutate in ["edit", "add", "delete"]:
        added = pkg.path / "extra.py"
        if mutate == "edit":
            helper.write_text("VALUE = 2\n")
        elif mutate == "add":
            added.write_text("EXTRA = True\n")
        else:
            helper.unlink()
        assert skala.package_hash(pkg) != original_hash
        assert "does not match" in reason(pkg, runs=[{**evaluation(pkg), "details": [
            {**d, "package_hash": original_hash} for d in evaluation(pkg)["details"]]}])
        helper.write_text("VALUE = 1\n")
        added.unlink(missing_ok=True)
    await skala.change_version(database, pkg, "founder", "approve", region="us-east", confirmed=True, review_token=review["review_token"])
    async with database.acquire() as conn:
        assert await conn.fetchval("SELECT used_at FROM tank.skill_source_reviews WHERE token=$1 AND tenant_id=$2", review["review_token"], PLATFORM)
        # Even if the same version becomes approvable again, the old token is spent.
        await conn.execute("UPDATE tank.skills SET state='staging' WHERE id=$1 AND version=$2", pkg.id, pkg.version)
    with pytest.raises(HTTPException, match="was used"):
        await skala.change_version(database, pkg, "founder", "approve", region="us-east", confirmed=True, review_token=review["review_token"])
    assert (await states(database, pkg.id))[pkg.version] == "staging"
