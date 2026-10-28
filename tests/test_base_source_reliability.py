"""Source scores, corridor and actual enrichment proof; fake HTTP/local PostgreSQL only."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import sys

import httpx
import pytest

from base_evidence import row_fields
from base_reliability import classify, prefer, read, scores, wilson_lower
from base_source_scores import SOURCES
from test_base_audit import audit_db, campaign, draw, checked, ROOT  # noqa: F401 (fixture)
from test_b3_base_room import _scripted, REFS
from pipeline import enrich_one, merge
from room import SkillClient

STAMP = "2026-10-28T00:00:00+00:00"
SITE = "https://acme.example/"
SOCIAL = "https://facebook.com/acme"


def test_complete_source_taxonomy_and_host_boundaries():
    urls = {"reference_file": "https://www.atf.gov/list", "own_site": SITE,
            "engine_registry": "registry:ffl", "social_profile": SOCIAL,
            "archive": "https://web.archive.org/web/1/example", "google_places": "https://google.com/maps/place/a",
            "opencorporates": "https://opencorporates.com/companies/a", "other_web": "https://directory.example/a"}
    for source, url in urls.items():
        assert classify(url, SITE, "registry:ffl" if source == "engine_registry" else None) == source
    assert classify("https://bucket.example/0926-ffl-list.csv", SITE, "reference_file") == "reference_file"
    assert set(urls) == set(SOURCES)
    for url in ("https://evil.example/google.com/maps", "https://google.com.evil.example/maps",
                "https://evil.example/?next=maps.google.com", "https://facebook.com.evil.example/acme"):
        assert classify(url, SITE) == "other_web"


def test_known_counts_all_sources_and_no_identifying_output():
    records = [{"record_id": str(i), "fields": {"phone": {"value": "fixture",
                "source_kind": source, "verified": True}}} for i, source in enumerate(SOURCES)]
    rows = scores([{"records": records, "field_verdicts": {str(i): {"phone": "correct"} for i in range(len(records))}}])
    assert {row["source"] for row in rows} == set(SOURCES)
    assert all(row["correct"] == row["checked"] == 1 and row["accuracy"] == 1 for row in rows)
    assert all(row["wilson_lower"] == pytest.approx(wilson_lower(1, 1)) for row in rows)
    assert "fixture" not in json.dumps(rows)


def test_deterministic_ties_and_unmeasured_fallback():
    first = {"value": "first", "source_url": SITE, "website": SITE}
    second = {"value": "second", "source_url": SOCIAL, "website": SITE}
    assert prefer([first, second], "phone", {}) is first
    equal = {("own_site", "phone"): .5, ("social_profile", "phone"): .5}
    assert prefer([first, second], "phone", equal) is first
    profile = {"phone": {**first, "confidence": 90}}
    merge(profile, {"phone": {**second, "confidence": 80}}, {})
    assert profile["phone"]["value"] == "first"
    evidence = {}
    merge(profile, {"phone": {**second, "confidence": 10}}, {("social_profile", "phone"): .8}, evidence)
    assert profile["phone"]["value"] == "second"
    assert len(evidence["phone"]["candidates"]) == 2


@pytest.mark.asyncio
async def test_room_pipeline_uses_scores_and_export_retains_both_sources(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents/base"))
    observations = [
        {"source_url": SITE, "checked_at": STAMP, "phones": ["512-555-0100"]},
        {"source_url": SOCIAL, "checked_at": STAMP, "phones": ["512-555-0199"]}]
    requests = []
    # A known, fully local field audit produces these scores: 50/100 vs 100/100.
    known = {"records": [], "field_verdicts": {}}
    for i in range(200):
        rid = str(i)
        source = "own_site" if i < 100 else "social_profile"
        known["records"].append({"record_id": rid, "fields": {"phone": {
            "value": "offline", "verified": True, "source_kind": source}}})
        known["field_verdicts"][rid] = {"phone": "correct" if i < 50 or i >= 100 else "wrong"}
    score_rows = scores([known])

    def handle(request):
        requests.append(request.url.path)
        assert request.headers["x-tank-key"] == "offline-fixture"
        if request.url.path.endswith("/source-reliability/room"):
            return httpx.Response(200, json={"scores": score_rows})
        skill = request.url.path.split("/")[-2]
        payload = json.loads(request.content)["input"]
        result = _scripted(skill, payload)
        if skill == "base.scrape_site":
            result["_base_observations"] = observations
        return httpx.Response(200, json=result)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        client = SkillClient(http, "https://tank.fixture", "offline-fixture")
        call = client.bind({key: "1.0.0" for key in REFS}, False, "offline-tenant")
        # Normalization happens during preparation and enrichment; read scores once.
        await call("base.normalize", {"name": "Offline fixture"})
        outcome = await enrich_one({"name": "Offline fixture", "phone": "512-555-0100"}, None, [], None, call, REFS)
    assert outcome.status == "done", outcome.error
    assert requests.count("/v1/base-product/source-reliability/room") == 1
    assert outcome.profile["phone"]["value"] == "512-555-0199"
    choice = outcome.passes["source_reliability"]["phone"]
    assert choice["wilson_lower"] == pytest.approx(wilson_lower(100, 100)) and len(choice["candidates"]) == 2
    fields = row_fields({"status": outcome.status, "profile": outcome.profile, "passes": outcome.passes})
    assert fields["phone"]["value"] == "512-555-0199"
    assert fields["phone"]["source_kind"] == "social_profile"
    assert len(fields["phone"]["items"]) == 2
    # Ranking cannot override an existing safety/verification failure.
    blocked = deepcopy(outcome.passes)
    blocked["2b"]["archive_date"] = "2020-01-01"
    assert not row_fields({"profile": outcome.profile, "passes": blocked})["phone"]["verified"]
    blocked = deepcopy(outcome.passes)
    blocked["7"]["checks"]["phone_matches_site"] = False
    assert not row_fields({"profile": outcome.profile, "passes": blocked})["phone"]["verified"]
    directory = os.environ.get("BASE_RELIABILITY_PROOF_DIR")
    if directory:
        Path(directory).mkdir(parents=True, exist_ok=True)
        (Path(directory) / "conflict.json").write_text(json.dumps({"offline_fixture": True, "scores": score_rows,
            "decision": choice, "exported_phone": fields["phone"]}, indent=2))


@pytest.mark.asyncio
async def test_room_corridor_has_counts_only_and_refuses_other_keys(audit_db):  # noqa: F811
    pool, rt, client = audit_db
    from base_product_fixtures import TENANT
    identity, _ = await campaign(pool)
    audit = (await draw(client, identity)).json()
    path = f"{ROOT}/{identity}/audits/{audit['id']}"
    params = {"tenant_id": str(TENANT)}
    csv = (await client.get(path + "/records.csv", params=params)).text
    response = await client.post(path + "/review", json={**params, "csv": checked(csv, ["correct"] * 200),
        "field_verdicts": {record["record_id"]: {"website": "correct"} for record in audit["records"]}})
    assert response.status_code == 200
    # No real credential; only the existing test fixture's corridor name/value.
    from unittest.mock import patch
    with patch.dict(os.environ, {"TANK_KEY_BASE": "room-fixture"}):
        response = await client.get("/v1/base-product/source-reliability/room", headers={"X-Tank-Key": "room-fixture"})
        assert response.status_code == 200
        rows = response.json()["scores"]
        assert rows and all(set(row) == {"source", "field", "correct", "wrong", "checked", "accuracy",
                                       "wilson_lower", "audits", "updated_at"} for row in rows)
        assert (await client.get("/v1/base-product/source-reliability/room")).status_code == 401
        old_region = rt.box_region
        rt.box_region = lambda: "za"
        try:
            assert (await client.get("/v1/base-product/source-reliability/room",
                                    headers={"X-Tank-Key": "room-fixture"})).status_code == 403
        finally:
            rt.box_region = old_region
    async with pool.acquire() as conn:
        assert await read(conn)
        assert await conn.fetchval("SELECT count(*) FROM tank.base_source_reliability WHERE owner_id<>$1", TENANT) == len(rows)


def test_mixed_record_checks_do_not_turn_correct_phone_into_wrong():
    record = {"record_id": "mixed", "fields": {
        name: {"value": "offline", "verified": True, "source_kind": "own_site"}
        for name in ("phone", "email", "website", "socials")}}
    audit = {"records": [record], "verdicts": {"mixed": "wrong"},
             "field_verdicts": {"mixed": {"phone": "correct", "email": "wrong", "socials": "unsure"}}}
    result = {row["field"]: row for row in scores([audit])}
    assert set(result) == {"phone", "email"}
    assert result["phone"]["accuracy"] == 1 and result["phone"]["checked"] == 1
    assert result["email"]["accuracy"] == 0 and result["email"]["wrong"] == 1
    assert scores([{**audit, "field_verdicts": {}}]) == []


@pytest.mark.asyncio
async def test_field_review_is_validated_immutable_and_recompute_failure_is_atomic(audit_db, monkeypatch):  # noqa: F811
    pool, _, client = audit_db
    from base_product_fixtures import TENANT
    import base_reliability
    identity, _ = await campaign(pool)
    audit = (await draw(client, identity)).json()
    path = f"{ROOT}/{identity}/audits/{audit['id']}"
    params = {"tenant_id": str(TENANT)}
    csv = (await client.get(path + "/records.csv", params=params)).text
    body = {**params, "csv": checked(csv)}
    record_id = audit["records"][0]["record_id"]
    for fields in ({"foreign": {"website": "correct"}}, {record_id: {"invented": "correct"}},
                   {record_id: {"website": "maybe"}}):
        assert (await client.post(path + "/review", json={**body, "field_verdicts": fields})).status_code == 422
    original = base_reliability.recompute
    async def fail(conn):
        raise RuntimeError("offline recompute failure")
    monkeypatch.setattr(base_reliability, "recompute", fail)
    with pytest.raises(RuntimeError, match="offline recompute failure"):
        await client.post(path + "/review", json=body)
    assert (await client.get(path, params=params)).json()["reviewed_at"] is None
    monkeypatch.setattr(base_reliability, "recompute", original)
    fields = {record_id: {"website": "correct", "phone": "wrong"}}
    result = await client.post(path + "/review", json={**body, "field_verdicts": fields})
    assert result.status_code == 200, result.text
    assert result.json()["field_verdicts"] == fields
    async with pool.acquire() as conn:
        rows = {row["field"]: row for row in await read(conn)}
    assert rows["website"]["correct"] == rows["phone"]["wrong"] == 1
    assert (await client.post(path + "/review", json={**body, "field_verdicts": fields})).status_code == 200
    assert (await client.post(path + "/review", json={**body, "field_verdicts": {}})).status_code == 409


@pytest.mark.asyncio
async def test_concurrent_audit_batches_keep_all_committed_field_counts(audit_db):  # noqa: F811
    import asyncio
    from base_product_fixtures import TENANT
    pool, _, client = audit_db
    identity, _ = await campaign(pool)
    bodies = []
    for seed in (41, 42):
        audit = (await draw(client, identity, seed)).json()
        path = f"{ROOT}/{identity}/audits/{audit['id']}"
        csv = (await client.get(path + "/records.csv", params={"tenant_id": str(TENANT)})).text
        bodies.append((path, {"tenant_id": str(TENANT), "csv": checked(csv),
            "field_verdicts": {record["record_id"]: {"website": "correct"} for record in audit["records"]}}))
    responses = await asyncio.gather(*(client.post(path + "/review", json=body) for path, body in bodies))
    assert all(response.status_code == 200 for response in responses)
    async with pool.acquire() as conn:
        rows = await read(conn)
    assert len(rows) == 1 and rows[0]["correct"] == rows[0]["checked"] == 400 and rows[0]["audits"] == 2
