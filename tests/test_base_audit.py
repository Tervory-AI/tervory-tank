"""Offline API and PostgreSQL proof; every record is an isolated test fixture."""
from __future__ import annotations

import asyncio
import csv
from datetime import datetime
import io
import json
import os
from pathlib import Path
import random
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
import uuid

import asyncpg
from fastapi import FastAPI
import httpx
import pytest
import pytest_asyncio

from base_audit import AuditStore, BANDS, measure
from base_product import build_router
from base_product_fixtures import AT, TENANT, OTHER, finished, raw
from base_repository import encoded
from agents.base.engines.ffl.reference import project

ROOT = "/v1/base-product/campaigns"
HEADERS = {"X-Tank-Key": "local-fixture", "X-Tervory-Admin": "fixture-founder"}
DT = datetime.fromisoformat(AT)


@pytest_asyncio.fixture
async def audit_db(monkeypatch):
    address = os.environ.get("BASE_TEST_DATABASE_URL") or os.environ.get("POOL_SCHEMA_DATABASE_URL")
    if not address:
        pytest.skip("Set BASE_TEST_DATABASE_URL or POOL_SCHEMA_DATABASE_URL to an isolated local PostgreSQL")
    parts = urlsplit(address)
    assert parts.hostname in {"localhost", "127.0.0.1"}
    name = "base_audit_" + uuid.uuid4().hex
    admin = await asyncpg.connect(address)
    await admin.execute(f'CREATE DATABASE "{name}"')
    pool = await asyncpg.create_pool(urlunsplit(parts._replace(path="/" + name)), min_size=1, max_size=5)
    try:
        async with pool.acquire() as conn:
            schema = (Path(__file__).resolve().parents[1] / "tank/schema.sql").read_text()
            await conn.execute(schema)
            await conn.execute(schema)
        monkeypatch.setenv("TANK_API_KEY", "local-fixture")
        monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "fixture-founder")
        rt = SimpleNamespace(pool=lambda: pool, box_region=lambda: "us-east")
        app = FastAPI()
        app.include_router(build_router(rt, background=False))
        # Any outbound HTTP would be a regression: data and arithmetic are local.
        def no_network(*args, **kwargs):
            raise AssertionError("Base audits must not call external services or models")
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", no_network)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture", headers=HEADERS) as client:
            yield pool, rt, client
    finally:
        await pool.close()
        await admin.execute(f'DROP DATABASE "{name}"')
        await admin.close()


async def campaign(pool, tenant=TENANT, n=240, *, scores=None, status="done", unverified=0):
    identity = uuid.uuid4()
    records = []
    async with pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.base_campaigns(tenant_id,id,request_id,name,selection,created_by)
            VALUES($1,$2,$3,'Offline audit fixture','{}','fixture-founder')""", tenant, identity, uuid.uuid4())
        for ordinal, state in enumerate(("CA", "TX")):
            task = uuid.uuid4()
            batch = f"fixture {identity} {state}"
            await conn.execute("""INSERT INTO tank.base_campaign_states
                (tenant_id,campaign_id,state,ordinal,batch,task_id,status,records_count,finished_at)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)""", tenant, identity, state, ordinal, batch, task, status,
                len(range(ordinal, n, 2)), DT if status in {"done", "failed"} else None)
            for i in range(ordinal, n, 2):
                row = finished(project(raw(i + 1, state)), tenant)
                row.update(task_id=task, batch=batch, confidence=scores[i % len(scores)] if scores else 80,
                           source_revision=f"fixture-revision-{i}")
                if i < unverified:
                    for field in row["fields"].values():
                        field.update(verified=False, value=None, reason="not_found")
                await conn.execute("""INSERT INTO agent_base.records
                    (id,tenant_id,task_id,batch,raw,profile,passes,confidence,status,created_at,updated_at)
                    VALUES($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7::jsonb,$8,'done',$9,$9)""",
                    row["id"], tenant, task, batch, encoded(row["raw"]), encoded(row["profile"]), encoded(row["passes"]), row["confidence"], DT)
                await conn.execute("""INSERT INTO tank.base_record_results
                    (tenant_id,record_id,task_id,batch,licence_key,state,licence_type,name,status,fields,source_revision,attempted_at,checked_at)
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,'done',$9::jsonb,$10,$11,$11)""", tenant, row["id"], task, batch,
                    row["licence_key"], state, row["licence_type"], row["name"], encoded(row["fields"]), row["source_revision"], DT)
                records.append(row)
    return identity, records


async def draw(client, campaign_id, seed=42, tenant=TENANT):
    return await client.post(f"{ROOT}/{campaign_id}/audits", json={"tenant_id": str(tenant), "seed": seed})


def checked(text, verdicts=None, mutate=None):
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    rows = list(reader)
    for index, row in enumerate(rows):
        row["verdict"] = verdicts[index] if verdicts else "correct"
    if mutate:
        mutate(rows)
    result = io.StringIO(newline="")
    writer = csv.DictWriter(result, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return result.getvalue()


@pytest.mark.parametrize(("correct", "wrong", "unsure", "low", "high"), [
    (180, 20, 0, .8505941875672826, .934329551330904),
    (171, 19, 10, .8491030549232077, .9350429215090166),
    (200, 0, 0, .9811546736227335, 1),
    (0, 200, 0, 0, .018845326377266575),
])
def test_accuracy_known_wilson_intervals(correct, wrong, unsure, low, high):
    verdicts = dict(enumerate(["correct"] * correct + ["wrong"] * wrong + ["unsure"] * unsure))
    result = measure(verdicts)
    assert result["accuracy"] == correct / (correct + wrong)
    assert result["confidence_interval"]["lower"] == pytest.approx(low)
    assert result["confidence_interval"]["upper"] == pytest.approx(high)
    assert result["denominator"] == correct + wrong
    assert result["unsure"] == unsure
    assert result["sample_accuracy_bounds"] == {"lower": correct / 200, "upper": (correct + unsure) / 200}


def test_no_resolved_verdicts_is_not_zero_accuracy():
    for verdicts in ({}, dict(enumerate(["unsure"] * 200))):
        result = measure(verdicts)
        assert result["accuracy"] is None and result["confidence_interval"] is None
        assert result["denominator"] == 0
        assert result["sample_accuracy_bounds"] == {"lower": 0, "upper": 1}


@pytest.mark.asyncio
async def test_seeded_sample_saved_sources_round_trip_and_accuracy(audit_db):
    pool, rt, client = audit_db
    identity, records = await campaign(pool)
    await campaign(pool, OTHER)
    response = await draw(client, identity)
    assert response.status_code == 200, response.text
    audit = response.json()
    assert audit["population_size"] == 240 and len(audit["records"]) == 200
    expected = random.Random(42).sample(sorted(records, key=lambda row: row["record_id"]), 200)
    assert [row["record_id"] for row in audit["records"]] == [str(row["record_id"]) for row in expected]
    assert {row["tenant_id"] for row in audit["records"]} == {str(TENANT)}
    assert audit["measurement"]["accuracy"] is None
    assert (await draw(client, identity)).json() == audit
    assert (await draw(client, identity, 43)).json()["records"] != audit["records"]
    path = f"{ROOT}/{identity}/audits/{audit['id']}"
    params = {"tenant_id": str(TENANT)}
    downloaded = await client.get(path + "/records.csv", params=params)
    assert downloaded.status_code == 200 and downloaded.headers["cache-control"] == "private, no-store"
    csv_rows = list(csv.DictReader(io.StringIO(downloaded.text.lstrip("\ufeff"))))
    assert len(csv_rows) == 200
    for row, record in zip(csv_rows, audit["records"]):
        assert row["record_id"] == record["record_id"]
        assert row["website_source_url"] == record["fields"]["website"]["source_url"]
        assert row["website_checked_at"] == AT
        assert row["email_source_url"].endswith("/contact")
        assert row["email_checked_at"] == AT
        assert row["record_checked_at"] == record["checked_at"]
        assert row["confidence"] == "80"
    # Source changes cannot alter a saved sample, its evidence, or its re-export.
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tank.base_record_results SET name='Later fixture result',fields='{}' WHERE tenant_id=$1", TENANT)
        await conn.execute("UPDATE agent_base.records SET confidence=0 WHERE tenant_id=$1", TENANT)
    fresh_store = AuditStore(rt)
    reopened = await fresh_store.get(TENANT, identity, uuid.UUID(audit["id"]))
    assert reopened["records"] == audit["records"]
    assert (await draw(client, identity)).json() == audit
    assert (await client.get(path + "/records.csv", params=params)).text == downloaded.text
    verdicts = ["correct"] * 171 + ["wrong"] * 19 + ["unsure"] * 10
    upload = checked(downloaded.text, verdicts, lambda rows: rows.reverse())
    reviewed = await client.post(path + "/review", json={**params, "csv": upload})
    assert reviewed.status_code == 200, reviewed.text
    saved = reviewed.json()
    assert saved["measurement"] == measure(dict(enumerate(verdicts)))
    assert saved["measurement"]["accuracy"] == .9
    assert saved["measurement"]["confidence_interval"] == pytest.approx({
        "lower": .8491030549232077, "upper": .9350429215090166})
    assert saved["reviewed_by"] == "fixture-founder" and saved["reviewed_at"]
    assert (await client.get(path, params=params)).json() == saved
    assert (await client.post(path + "/review", json={**params, "csv": upload})).json() == saved
    changed = await client.post(path + "/review", json={**params, "csv": checked(downloaded.text)})
    assert changed.status_code == 409
    exported = await client.get(path + "/records.csv", params=params)
    assert [row["verdict"] for row in csv.DictReader(io.StringIO(exported.text.lstrip("\ufeff")))] == verdicts
    if proof_dir := os.environ.get("BASE_AUDIT_PROOF_DIR"):
        proof = Path(proof_dir)
        proof.mkdir(parents=True, exist_ok=True)
        (proof / "api-proof.json").write_text(json.dumps({
            "environment": "isolated offline fixture; not production",
            "sample_response": {key: audit[key] for key in ("tenant_id", "campaign_id", "id", "seed", "population_size", "population_sha256", "sampling_method")},
            "sampled_records": len(audit["records"]), "csv_rows": len(csv_rows),
            "first_exported_record": csv_rows[0], "review_response": saved["measurement"],
            "same_seed_same_saved_audit": True, "reopened_after_source_change_unchanged": True,
        }, indent=2) + "\n")


@pytest.mark.asyncio
async def test_two_tenant_and_campaign_isolation_and_all_routes_guarded(audit_db):
    pool, _, client = audit_db
    first, a_records = await campaign(pool)
    second, b_records = await campaign(pool, OTHER)
    third, _ = await campaign(pool)
    a = (await draw(client, first)).json()
    b = (await draw(client, second, tenant=OTHER)).json()
    assert {r["record_id"] for r in a["records"]}.isdisjoint({str(r["id"]) for r in b_records})
    assert {r["record_id"] for r in b["records"]}.isdisjoint({str(r["id"]) for r in a_records})
    assert (await draw(client, first, tenant=OTHER)).status_code == 404
    assert (await client.get(f"{ROOT}/{first}/confidence-histogram", params={"tenant_id": str(OTHER)})).status_code == 404
    base = f"{ROOT}/{first}/audits/{a['id']}"
    csv_text = (await client.get(base + "/records.csv", params={"tenant_id": str(TENANT)})).text
    for tenant, campaign_id in ((OTHER, first), (TENANT, third)):
        path = f"{ROOT}/{campaign_id}/audits/{a['id']}"
        for suffix in ("", "/records.csv"):
            assert (await client.get(path + suffix, params={"tenant_id": str(tenant)})).status_code == 404
        assert (await client.post(path + "/review", json={"tenant_id": str(tenant), "csv": checked(csv_text)})).status_code == 404
    routes = [
        ("POST", f"{ROOT}/{first}/audits", {"json": {"tenant_id": str(TENANT), "seed": 42}}),
        ("GET", base, {"params": {"tenant_id": str(TENANT)}}),
        ("GET", base + "/records.csv", {"params": {"tenant_id": str(TENANT)}}),
        ("POST", base + "/review", {"json": {"tenant_id": str(TENANT), "csv": checked(csv_text)}}),
        ("GET", f"{ROOT}/{first}/confidence-histogram", {"params": {"tenant_id": str(TENANT)}}),
    ]
    for method, path, kwargs in routes:
        for headers, code in (({"X-Tervory-Admin": ""}, 404), ({"X-Tervory-Admin": "client-user"}, 404),
                              ({"X-Tank-Key": "wrong-fixture"}, 401)):
            response = await client.request(method, path, headers=headers, **kwargs)
            assert response.status_code == code, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("problem", ["short", "unfinished", "uncollected", "stale", "bad_score"])
async def test_incomplete_population_refused_without_saving(audit_db, problem):
    pool, _, client = audit_db
    identity, records = await campaign(pool, n=199 if problem == "short" else 240,
                                       status="running" if problem == "unfinished" else "done")
    async with pool.acquire() as conn:
        if problem == "uncollected":
            await conn.execute("DELETE FROM tank.base_record_results WHERE tenant_id=$1 AND record_id=$2", TENANT, records[0]["id"])
        if problem == "stale":
            await conn.execute("UPDATE agent_base.records SET updated_at=updated_at+interval '1 second' WHERE tenant_id=$1 AND id=$2", TENANT, records[0]["id"])
        if problem == "bad_score":
            await conn.execute("UPDATE agent_base.records SET confidence=101 WHERE tenant_id=$1 AND id=$2", TENANT, records[0]["id"])
    assert (await draw(client, identity)).status_code == 409
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM tank.base_audits WHERE tenant_id=$1", TENANT) == 0


@pytest.mark.asyncio
async def test_checked_csv_rejects_damage_atomically_and_preserves_formula_escaping(audit_db):
    pool, _, client = audit_db
    identity, _ = await campaign(pool, n=200)
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tank.base_record_results SET name='=1+1' WHERE tenant_id=$1", TENANT)
    audit = (await draw(client, identity)).json()
    path = f"{ROOT}/{identity}/audits/{audit['id']}"
    params = {"tenant_id": str(TENANT)}
    original = (await client.get(path + "/records.csv", params=params)).text
    assert "'=1+1" in original
    bad = [
        checked(original, mutate=lambda rows: rows.pop()),
        checked(original, mutate=lambda rows: rows.append(rows[0])),
        checked(original, mutate=lambda rows: rows[0].update(record_id=str(uuid.uuid4()))),
        checked(original, mutate=lambda rows: rows[0].update(audit_id=str(uuid.uuid4()))),
        checked(original, mutate=lambda rows: rows[0].update(verdict="")),
        checked(original, mutate=lambda rows: rows[0].update(verdict="probably")),
        checked(original, mutate=lambda rows: rows[0].update(website_source_url="https://edited.example/")),
        checked(original, mutate=lambda rows: rows[0].update(website_checked_at="2020-01-01")),
        "record_id,verdict\n", checked(original).replace("record_id,", "verdict,", 1),
        '"unterminated',
    ]
    for text in bad:
        response = await client.post(path + "/review", json={**params, "csv": text})
        assert response.status_code == 422, response.text
        saved = (await client.get(path, params=params)).json()
        assert saved["verdicts"] == {} and saved["reviewed_at"] is None
    assert (await client.post(path + "/review", json={**params, "csv": checked(original)})).status_code == 200


@pytest.mark.asyncio
async def test_histogram_boundaries_campaign_scope_missing_scores_and_unverified(audit_db):
    pool, _, client = audit_db
    # Two of every boundary in each state; one full cycle is unverified.
    scores = [value for value in (0, 39, 40, 59, 60, 79, 80, 100) for _ in range(2)]
    identity, records = await campaign(pool, n=48, scores=scores, unverified=16)
    await campaign(pool)  # Same tenant, another campaign: must not inflate totals.
    await campaign(pool, OTHER)
    path = f"{ROOT}/{identity}/confidence-histogram"
    response = await client.get(path, params={"tenant_id": str(TENANT)})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["verified_records"] == 32 and result["missing_confidence"] == 0
    assert result["bands"] == [{"min": low, "max": high, "count": 8} for low, high in BANDS]
    for state in result["states"]:
        assert state["verified_records"] == 16 and [r["count"] for r in state["bands"]] == [4] * 4
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM agent_base.records WHERE tenant_id=$1 AND id=$2", TENANT, records[-1]["id"])
    result = (await client.get(path, params={"tenant_id": str(TENANT)})).json()
    assert result["verified_records"] == 32 and result["missing_confidence"] == 1
    assert sum(row["count"] for row in result["bands"]) == 31
    if proof_dir := os.environ.get("BASE_AUDIT_PROOF_DIR"):
        Path(proof_dir, "histogram-proof.json").write_text(json.dumps(result, indent=2) + "\n")


@pytest.mark.asyncio
async def test_concurrent_draws_are_one_saved_sample_and_request_validation(audit_db):
    pool, _, client = audit_db
    identity, _ = await campaign(pool)
    responses = await asyncio.gather(*(draw(client, identity) for _ in range(3)))
    assert all(response.status_code == 200 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 1
    for seed in (-1, 2**63, True, 1.5, "42"):
        assert (await draw(client, identity, seed)).status_code == 422
    assert (await draw(client, uuid.uuid4())).status_code == 404


@pytest.mark.asyncio
async def test_sample_uses_latest_verified_campaign_records_without_cross_campaign_dedup(audit_db):
    pool, _, client = audit_db
    identity, records = await campaign(pool, unverified=20)
    # The other campaign has all the same licence keys and later check dates.
    other_campaign, other_records = await campaign(pool)
    async with pool.acquire() as conn:
        await conn.execute("""UPDATE tank.base_record_results r SET checked_at=checked_at+interval '1 day'
            FROM tank.base_campaign_states s WHERE r.tenant_id=$1 AND s.tenant_id=$1 AND s.campaign_id=$2
                AND r.task_id=s.task_id""", TENANT, other_campaign)
        # Give two rows in this campaign the same key. Only the newest is eligible.
        older, newer = records[20:22]
        await conn.execute("""UPDATE tank.base_record_results SET licence_key=$3,checked_at=checked_at+interval '1 hour'
            WHERE tenant_id=$1 AND record_id=$2""", TENANT, newer["id"], older["licence_key"])
    audit = (await draw(client, identity)).json()
    assert audit["population_size"] == 219
    selected = {row["record_id"] for row in audit["records"]}
    excluded = {str(row["id"]) for row in records if not row["fields"]["website"]["verified"]}
    excluded |= {str(row["id"]) for row in other_records} | {str(older["id"])}
    assert not selected & excluded
    assert len({row["licence_key"] for row in audit["records"]}) == 200
    histogram = (await client.get(f"{ROOT}/{identity}/confidence-histogram", params={"tenant_id": str(TENANT)})).json()
    assert histogram["verified_records"] == 219
    assert sum(state["verified_records"] for state in histogram["states"]) == 219


@pytest.mark.asyncio
async def test_simultaneous_reviews_do_not_silently_overwrite_each_other(audit_db):
    pool, _, client = audit_db
    identity, _ = await campaign(pool, n=200)
    audit = (await draw(client, identity)).json()
    path = f"{ROOT}/{identity}/audits/{audit['id']}"
    params = {"tenant_id": str(TENANT)}
    original = (await client.get(path + "/records.csv", params=params)).text
    responses = await asyncio.gather(*(client.post(path + "/review", json={**params, "csv": text}) for text in (
        checked(original), checked(original, ["wrong"] * 200))))
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response.json() for response in responses if response.status_code == 200)
    assert (await client.get(path, params=params)).json() == winner


@pytest.mark.asyncio
async def test_empty_histogram_is_zero_bands_for_each_state_and_region_guard(audit_db):
    pool, rt, client = audit_db
    identity, _ = await campaign(pool, n=0, status="waiting")
    response = await client.get(f"{ROOT}/{identity}/confidence-histogram", params={"tenant_id": str(TENANT)})
    assert response.status_code == 200
    histogram = response.json()
    assert histogram["verified_records"] == 0
    assert all(band["count"] == 0 for band in histogram["bands"])
    assert [state["state"] for state in histogram["states"]] == ["CA", "TX"]
    assert all(state["verified_records"] == 0 for state in histogram["states"])
    rt.box_region = lambda: "af-south"
    assert (await client.get(f"{ROOT}/{identity}/confidence-histogram", params={"tenant_id": str(TENANT)})).status_code == 403
    assert (await draw(client, identity)).status_code == 403


# Job 6 (F8): per-source reliability from reviewed audits.
from base_reliability import classify, prefer, scores, wilson_lower  # noqa: E402


def test_source_kinds_from_field_urls():
    site = "https://www.smitharms.com/"
    assert classify("https://smitharms.com/contact", site) == "own_site"
    assert classify("https://shop.smitharms.com/about", site) == "own_site"
    assert classify("https://www.facebook.com/smitharms", site) == "social_profile"
    assert classify("https://web.archive.org/web/2024/https://smitharms.com/", site) == "archive"
    assert classify("https://maps.google.com/?cid=1", site) == "google_places"
    assert classify("https://opencorporates.com/companies/us_nh/1", site) == "opencorporates"
    assert classify("https://directory.example.org/smith", site) == "other_web"
    assert classify(None, site) is None and classify("not a url", site) is None


def test_wilson_lower_bound_keeps_small_samples_from_looking_perfect():
    assert wilson_lower(0, 0) is None
    assert wilson_lower(3, 3) < .5 < wilson_lower(200, 200)
    assert wilson_lower(180, 200) == pytest.approx(.8505941875672826)


def _record(rid, site, email_url, verified=True):
    return {"record_id": rid, "fields": {
        "website": {"value": site, "source_url": site, "verified": verified},
        "email": {"value": "a@b.c", "source_url": email_url, "verified": verified},
        "phone": {"value": None, "source_url": None, "verified": False},
        "socials": {"value": None, "source_url": None, "verified": False}}}


def test_scores_count_resolved_verdicts_per_source_and_field_only():
    site = "https://smitharms.com/"
    audit = {"records": [_record("1", site, site + "contact"), _record("2", site, "https://facebook.com/smith"),
                         _record("3", site, site + "contact"), _record("4", site, site + "contact", verified=False)],
             "field_verdicts": {str(i): {name: verdict for name in ("website", "email")}
                                for i, verdict in ((1, "correct"), (2, "wrong"), (3, "unsure"), (4, "correct"))}}
    rows = {(row["source"], row["field"]): row for row in scores([audit, {"records": [], "verdicts": {}}])}
    assert set(rows) == {("own_site", "website"), ("own_site", "email"), ("social_profile", "email")}
    assert rows[("own_site", "website")] | {} == {**rows[("own_site", "website")], "correct": 1, "wrong": 1, "checked": 2, "audits": 1}
    assert rows[("own_site", "email")]["correct"] == 1 and rows[("own_site", "email")]["wrong"] == 0
    assert rows[("social_profile", "email")]["wrong"] == 1 and rows[("social_profile", "email")]["accuracy"] == 0
    # Counts only: no tenant, record id, URL or value leaves the audit.
    assert all(set(row) == {"source", "field", "correct", "wrong", "checked", "accuracy", "wilson_lower", "audits"}
               for row in rows.values())


def test_higher_scoring_source_wins_and_unscored_ranks_below_scored():
    table = {("own_site", "email"): .9, ("social_profile", "email"): .4}
    site = "https://smitharms.com/"
    social = {"value": "x@y.z", "source_url": "https://facebook.com/smith", "website": site}
    own = {"value": "a@b.c", "source_url": site + "contact", "website": site}
    other = {"value": "o@p.q", "source_url": "https://directory.example.org/smith", "website": site}
    assert prefer([social, own], "email", table) is own
    assert prefer([other, social], "email", table) is social
    assert prefer([other], "email", table) is other


@pytest.mark.asyncio
async def test_review_recomputes_platform_scores_and_route_is_guarded(audit_db):
    pool, _, client = audit_db
    identity, _ = await campaign(pool)
    audit = (await draw(client, identity)).json()
    path = f"{ROOT}/{identity}/audits/{audit['id']}"
    params = {"tenant_id": str(TENANT)}
    exported = (await client.get(path + "/records.csv", params=params)).text
    verdicts = ["correct"] * 171 + ["wrong"] * 19 + ["unsure"] * 10
    field_verdicts = {record["record_id"]: {name: verdicts[index] for name, value in record["fields"].items()
                      if value.get("verified")} for index, record in enumerate(audit["records"])}
    assert (await client.post(path + "/review", json={**params, "csv": checked(exported, verdicts),
                                                      "field_verdicts": field_verdicts})).status_code == 200
    saved = (await client.get(path, params=params)).json()
    expected = scores([saved])
    response = await client.get("/v1/base-product/source-reliability")
    assert response.status_code == 200, response.text
    got = response.json()["scores"]
    assert {(row["source"], row["field"], row["correct"], row["wrong"]) for row in got} == \
        {(row["source"], row["field"], row["correct"], row["wrong"]) for row in expected}
    own = next(row for row in got if row["source"] == "own_site" and row["field"] == "website")
    assert own["checked"] == 190 and own["correct"] == 171 and own["audits"] == 1
    assert own["wilson_lower"] == pytest.approx(.8491030549232077)
    # Nothing identifying is stored.
    async with pool.acquire() as conn:
        columns = {row["column_name"] for row in await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='tank' AND table_name='base_source_reliability'")}
    assert not columns & {"tenant_id", "record_id", "source_url", "value"}
    # Same guards as every audit route.
    no_admin = await client.get("/v1/base-product/source-reliability", headers={"X-Tervory-Admin": "someone-else"})
    no_key = await client.get("/v1/base-product/source-reliability", headers={"X-Tank-Key": "wrong"})
    assert no_admin.status_code in {403, 404} and no_key.status_code in {401, 403, 404}
