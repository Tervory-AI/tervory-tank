"""Nightly ATF joins use synthetic list/scrape fixtures and no live requests."""

import json
import uuid
from contextlib import asynccontextmanager
from datetime import date
from unittest.mock import AsyncMock

import httpx
import pytest

from test_base_gold_sources import ROOT, load
from base_gold import build, gold_sources
from base_gold.gold_sources import PLATFORM_TENANT, candidates, read_candidates
from base_gold.observations import observation
from base_gold.ffl.atf_gold import fetch_list, published

TODAY = date(2026, 10, 20)
SOURCE = "https://www.atf.gov/resource-center/docs/1026-ffl-list-complete.txt"
INGEST = load("gold_atf_ingest_contract", ROOT / "tank/skills/ffl.ingest/1.0.0/run.py")


def listing(number=0):
    return published({
        "LIC_REGN": "1", "LIC_DIST": "57", "LIC_CNTY": "029", "LIC_TYPE": "01",
        "LIC_XPRDTE": "7A", "LIC_SEQN": str(10000 + number),
        "LICENSE_NAME": f"Published Licensee {number}", "BUSINESS_NAME": "",
        "PREMISE_STREET": f"{10 + number} Home Lane", "PREMISE_CITY": "Boston",
        "PREMISE_STATE": "MA", "PREMISE_ZIP_CODE": "02110", "VOICE_PHONE": f"61755501{number:02}",
        "EMAIL": "NEVER_EXPORT", "SOCIALS": "NEVER_EXPORT",
    })


def observed(number=0):
    row = listing(number)
    return {
        "raw": row,
        "observation": {
            "website": f"https://business{number}.example",
            "source_url": f"https://business{number}.example/contact",
            "observed_on": TODAY.isoformat(), "status": 200, "blocked": False,
            "phones": [row["voice_phone"]],
            "addresses": [{
                "address": row["premise_street"], "city": row["premise_city"],
                "state": row["premise_state"], "zip": row["premise_zip_code"],
            }],
            "people": "NEVER_EXPORT", "socials": "NEVER_EXPORT",
        },
    }


async def call(skill, payload):
    assert skill == "ffl.ingest"
    assert "website" not in payload
    return await INGEST.run(payload, None)


async def joined(rows=None, observations=None):
    return await build.join_list(
        rows if rows is not None else [listing(number) for number in range(6)],
        observations if observations is not None else [observed(number) for number in range(6)],
        call, source_url=SOURCE, snapshot=TODAY.replace(day=1), today=TODAY,
    )


@pytest.mark.asyncio
async def test_code_builds_file_and_public_list_only_labels(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    rows = await joined()
    assert len(rows) == 6
    assert "NEVER_EXPORT" not in json.dumps(rows)
    build.publish(rows, region="us-east")
    stored = tmp_path / "gold/us-east/official-matches.jsonl"
    assert [json.loads(line) for line in stored.read_text().splitlines()] == rows
    labels = candidates(rows, region="us-east", today=TODAY)
    verify = [label for label in labels if label["skill_id"] == "base.verify"]
    assert len(verify) == 8
    assert sum(not label["expected"]["checks"]["phone_matches_site"] for label in verify) == 2
    for label in labels:
        assert label["public"] is True
        assert "2026-10-01" in label["label_source"]
        assert "ATF Federal Firearms Licensees" in label["label_source"]
    verifier = load("gold_verify_contract", ROOT / "tank/skills/base.verify/1.0.0/run.py")
    for label in verify:
        result = await verifier.run(label["input"], None)
        assert result["checks"] == label["expected"]["checks"]
        if not label["expected"]["checks"]["phone_matches_site"]:
            assert label["input"]["raw"]["phone"] != label["input"]["profile"]["phones"]["value"][0]
            assert label["input"]["raw"]["address"] != label["input"]["profile"]["address"]["value"]
    assert "NEVER_EXPORT" not in json.dumps(labels)


@pytest.mark.asyncio
async def test_inactive_nonmatches_and_copied_inputs_never_join():
    rows = [listing()]
    rows[0]["lic_xprdte"] = "5M"
    old = observed()
    old["raw"] = rows[0]
    assert await joined(rows, [old]) == []
    wrong = observed()
    wrong["observation"]["phones"] = ["6175550199"]
    wrong["observation"]["addresses"][0]["address"] = "Unrelated street"
    assert await joined([listing()], [wrong]) == []
    wrong["profile"] = {"phone": listing()["voice_phone"], "address": listing()["premise_street"]}
    assert await joined([listing()], [wrong]) == []
    wrong["observation"] = {}
    assert await joined([listing()], [wrong]) == []


@pytest.mark.asyncio
async def test_address_only_match_drops_other_phone_and_socials():
    record = observed()
    record["observation"]["phones"] = ["6175550199"]
    rows = await joined([listing()], [record])
    assert len(rows) == 1 and "phone" not in rows[0]["site"]
    assert "6175550199" not in json.dumps(rows)
    labels = candidates(rows, region="us-east", today=TODAY)
    assert {label["skill_id"] for label in labels} == {"base.find_site", "base.normalize", "base.resolve"}


@pytest.mark.asyncio
async def test_no_negative_when_observed_contacts_are_ambiguous():
    observations = [observed(number) for number in range(6)]
    for record in observations:
        record["observation"]["phones"].append("6175550199")
    labels = candidates(await joined(observations=observations), region="us-east", today=TODAY)
    assert all(label["expected"]["checks"]["phone_matches_site"] for label in labels if label["skill_id"] == "base.verify")


@pytest.mark.asyncio
async def test_address_spelling_difference_is_not_a_negative():
    rows = await joined()
    for number, row in enumerate(rows):
        address = "10 Main St" if number % 2 else "10 Main Street"
        row["official"]["address"] = row["site"]["address"] = address
    labels = candidates(rows, region="us-east", today=TODAY)
    assert all(label["expected"]["checks"]["phone_matches_site"] for label in labels if label["skill_id"] == "base.verify")


def test_observations_come_only_from_scraped_pages():
    html = '<script type="application/ld+json">' + json.dumps({
        "@type": "PostalAddress", "streetAddress": "10 Home Lane",
        "addressLocality": "Boston", "addressRegion": "MA", "postalCode": "02110",
    }) + "</script>"
    scraped = {"pages": ["https://business.example/contact"], "text": "Contact the store",
               "phones": ["6175550100"], "html": html}
    saved = observation("https://business.example", scraped)
    assert saved["addresses"][0]["address"] == "10 Home Lane"
    assert saved["phones"] == ["6175550100"]
    assert observation("https://business.example", {**scraped, "error": "blocked"}) is None
    assert observation("https://business.example", {**scraped, "text": "CAPTCHA"}) is None
    assert observation("https://business.example", {**scraped, "pages": ["https://other.example"]}) is None


@pytest.mark.asyncio
async def test_fetches_published_list_with_robots_and_snapshot_date():
    requested = []
    row = listing()
    content = "\t".join(row) + "\n" + "\t".join(row.values()) + "\n"

    async def handler(request):
        requested.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if request.url.path.endswith(".txt"):
            return httpx.Response(200, text=content)
        return httpx.Response(200, text=f'<a href="{SOURCE}">Complete list</a>')

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        rows, source, snapshot = await fetch_list(http, TODAY)
    assert rows == [row] and source == SOURCE and snapshot == date(2026, 10, 1)
    assert requested[0].endswith("/robots.txt")


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [
    (200, "User-agent: *\nDisallow: /"), (403, "denied"), (200, "User-agent: *\nAllow: /"),
])
async def test_robots_and_challenges_are_not_bypassed(response):
    requested = []

    async def handler(request):
        requested.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(response[0], text=response[1])
        return httpx.Response(200, text="Verify you are human CAPTCHA")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(ValueError):
            await fetch_list(http, TODAY)
    assert len(requested) <= 2


@pytest.mark.asyncio
async def test_nightly_scopes_reads_pins_ingest_and_publishes(monkeypatch, tmp_path):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return TODAY

    monkeypatch.setattr(build, "date", FixedDate)
    monkeypatch.setattr(gold_sources, "date", FixedDate)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TANK_REGION", "us-east")
    conn = AsyncMock()
    conn.fetchval.return_value = True
    record = observed()
    record["observation"]["observed_on"] = TODAY.isoformat()
    conn.fetch.return_value = [{"raw": json.dumps(record["raw"]), "observation": json.dumps(record["observation"])}]

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield conn

    class Skills:
        approved = AsyncMock(return_value="1.0.0")

        def bind(self, versions, preview, tenant):
            assert versions == {"ffl.ingest": "1.0.0"} and preview is False and tenant == PLATFORM_TENANT
            return call

    fetch = AsyncMock(return_value=([listing()], SOURCE, TODAY.replace(day=1)))
    monkeypatch.setattr(build, "fetch_list", fetch)
    assert (await build.nightly(Pool(), object(), Skills()))["matches"] == 1
    assert conn.fetch.await_args.args[1] == uuid.UUID(PLATFORM_TENANT)
    assert "tenant_id=$1" in conn.fetch.await_args.args[0]
    assert len(read_candidates(limit=200, region="us-east")) == 4
    assert "pg_advisory_unlock" in conn.execute.await_args.args[0]
    path = tmp_path / "gold/us-east/official-matches.jsonl"
    previous = path.read_bytes()
    fetch.side_effect = ValueError("official source unavailable")
    with pytest.raises(ValueError, match="official source unavailable"):
        await build.nightly(Pool(), object(), Skills())
    assert path.read_bytes() == previous
    assert "pg_advisory_unlock" in conn.execute.await_args.args[0]
    monkeypatch.setenv("TANK_REGION", "za")
    fetch.reset_mock()
    assert (await build.nightly(Pool(), object(), Skills()))["status"] == "skipped"
    fetch.assert_not_called()


def test_nightly_is_registered_for_platform_only():
    module = load("base_gold_nightly_app", ROOT / "agents/base/app.py")
    schedule = next(item for item in module.app.state.schedules if item["kind"] == "gold.nightly")
    assert schedule == {"kind": "gold.nightly", "tenant_id": PLATFORM_TENANT, "cron": "15 1 * * *", "input": {}}
    assert "gold.nightly" in module.app.state.handlers


@pytest.mark.asyncio
async def test_nightly_handler_refuses_non_platform_tenant(monkeypatch):
    from types import SimpleNamespace

    module = load("base_gold_nightly_auth_app", ROOT / "agents/base/app.py")
    builder = AsyncMock()
    monkeypatch.setattr(module, "nightly", builder)
    with pytest.raises(ValueError, match="platform tenant"):
        await module.gold_nightly(SimpleNamespace(tenant_id=str(uuid.uuid4())))
    builder.assert_not_called()
