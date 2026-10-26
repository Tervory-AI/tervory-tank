"""Client evidence wording, revision provenance and caller-selected engines."""
import copy
import inspect
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/market_lab"))
from core.evidence import answer, document, document_page, latest_checks, overview
from core.http import build_router
from core.jobs import perform_refresh
from core.ledger import MemoryLedger
from feeds.geo import area_label
from feeds.presentation import observation_label, unit_label

TENANT = "00000000-0000-0000-0000-000000000001"
FIXTURES = str(ROOT / "tests/fixtures/feeds")


@pytest.mark.parametrize("area,title,expected", [
    ("06037", "Population, Los Angeles County, California", "Los Angeles County, California"),
    ("06001", "Active listings in Alameda", "Alameda, California"),
    ("06037", "Active listings in Los Angeles", "Los Angeles, California"),
    ("48201", "Active listings in Harris", "Harris, Texas"),
])
def test_every_stored_county_title_pattern_names_its_place(area, title, expected):
    assert area_label(area, "county", title) == expected


@pytest.mark.parametrize("value,unit,expected", [
    ("1", "listings", "listing"), ("2", "listings", "listings"),
    ("0", "listings", "listings"), ("1.0", "listings", "listing"),
    ("1", "persons", "person"), ("2", "persons", "people"),
    ("1", "checks", "check"), ("2", "checks", "checks"),
    ("1", "holders", "holder"), ("2", "holders", "holders"),
    ("1", "inches", "inch"), ("2", "inches", "inches"),
    ("1", "degrees F", "degree Fahrenheit"), ("2", "degrees F", "degrees Fahrenheit"),
    ("1", "TEU", "20-foot container unit"), ("2", "TEU", "20-foot container units"),
])
def test_unit_grammar(value, unit, expected):
    assert unit_label(value, unit) == expected


@pytest.mark.parametrize("title,expected", [
    ("PRCP in CA", "Precipitation in California"),
    ("TAVG in CA", "Average temperature in California"),
    ("01 checks in CA", "Checks in California (source category 01)"),
    ("Active listings in CA", "Active listings in California"),
    ("Paid licence holders in CA, 2022", "Paid licence holders in California, 2022"),
])
def test_measurement_names_explain_source_codes(title, expected):
    assert observation_label({"title": title, "geo": "CA", "geo_level": "state"}) == expected


@pytest.mark.asyncio
async def test_every_county_row_and_singular_listing_in_the_real_fixture_answer():
    ledger = MemoryLedger()
    await perform_refresh(tenant_id=TENANT, engine="ffl", ledger=ledger, fixtures=FIXTURES)
    seen = set()
    for check in await latest_checks(ledger, TENANT, fixtures=True):
        if not check["document_id"]:
            continue
        page = await document_page(ledger, TENANT, check["document_id"], fixtures=True)
        for point in page["points"]:
            if point["geo_level"] == "county":
                assert "not named" not in point["geo_name"]
                seen.add(point["title"])
    assert seen == {"Population, Los Angeles County, California", "Active listings in Alameda",
                    "Active listings in Los Angeles", "Active listings in Harris"}
    result = await answer(ledger, TENANT, "Active listings in Alameda", fixtures=True)
    assert any(": 1 listing (" in fact["text"] for fact in result["facts"])
    assert all(": 1 listings (" not in fact["text"] for fact in result["facts"])
    plural = await answer(ledger, TENANT, "Active listings in California", fixtures=True)
    assert any(": 2 listings (" in fact["text"] for fact in plural["facts"])


@pytest.mark.asyncio
async def test_revisions_are_labelled_and_only_the_current_value_answers():
    ledger = MemoryLedger()
    await perform_refresh(tenant_id=TENANT, engine="ffl", source="census_population", ledger=ledger, fixtures=FIXTURES)
    ident = (await latest_checks(ledger, TENANT, fixtures=True))[0]["document_id"]
    original = copy.deepcopy(await document(ledger, TENANT, ident, fixtures=True))
    page = await document_page(ledger, TENANT, ident, fixtures=True)
    california = [p for p in page["points"] if p["geo"] == "06"]
    assert [(p["value"], p["revision_label"]) for p in california] == [
        ("100", "Earlier figure (acs-v1)"), ("110", "Current figure (acs-v2)"),
    ]
    result = await answer(ledger, TENANT, "Population in California", fixtures=True)
    assert any(": 110 people (" in fact["text"] for fact in result["facts"])
    assert all(": 100 " not in fact["text"] for fact in result["facts"])
    assert await document(ledger, TENANT, ident, fixtures=True) == original
    # An older citation still opens its original row, explicitly marked earlier.
    earlier = await document_page(ledger, TENANT, ident, 0, fixtures=True)
    assert earlier["points"][0]["value"] == "100"
    assert earlier["points"][0]["revision_label"].startswith("Earlier figure")
    # Version order is collection order, not lexical sorting or value magnitude.
    saved = ledger.feed_documents[0]
    newest = {**saved["points"][0], "revision": "acs-v10"}
    saved["points"] += [{**newest, "series_id": f"padding-{i}"} for i in range(195)] + [newest]
    later = await document_page(ledger, TENANT, ident, 200, fixtures=True)
    assert later["points"][0]["value"] == "100"
    assert later["points"][0]["revision_label"] == "Current figure (acs-v10)"
    result = await answer(ledger, TENANT, "Population in California", fixtures=True)
    assert all(": 110 " not in fact["text"] for fact in result["facts"])


def test_core_contains_no_engine_name_and_defaults_to_none():
    engines = {path.name for path in (ROOT / "agents/market_lab/engines").iterdir() if path.is_dir() and not path.name.startswith("_")}
    for source in (ROOT / "agents/market_lab/core").glob("*.py"):
        assert all(name not in source.read_text() for name in engines), source.name
    assert inspect.signature(overview).parameters["engine"].default is None
    assert inspect.signature(build_router).parameters["engine"].default is None


@pytest.mark.asyncio
async def test_missing_engine_never_defaults_to_an_industry():
    with pytest.raises(ValueError, match="feed plan"):
        await overview(MemoryLedger(), TENANT)
    def no_database():
        raise AssertionError("An unconfigured feed plan must not touch the database")
    app = FastAPI()
    app.include_router(build_router(key_ok=lambda _: True, ledger_context=no_database))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for operation in ("overview", "refresh"):
            response = await client.post(f"/market/{operation}", json={"tenant_id": TENANT})
            assert response.status_code == 503


@pytest.mark.asyncio
async def test_http_forwards_the_callers_engine_to_overview_and_the_queued_job(monkeypatch):
    operations = []
    @asynccontextmanager
    async def transaction():
        yield
    class Connection:
        def transaction(self): return transaction()
        async def execute(self, sql, *args): operations.append((sql, args))
        async def fetchval(self, sql, *args): return None
    @asynccontextmanager
    async def ledger_context():
        yield SimpleNamespace(conn=Connection())
    async def read_overview(ledger, tenant, engine):
        assert tenant == TENANT and engine == "another-case"
        return {"feeds": [], "on_count": 0}
    monkeypatch.setattr("core.http.overview", read_overview)
    app = FastAPI()
    app.include_router(build_router(key_ok=lambda _: True, ledger_context=ledger_context, engine="another-case"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/market/overview", json={"tenant_id": TENANT})).status_code == 200
        assert (await client.post("/market/refresh", json={"tenant_id": TENANT})).status_code == 200
    inserts = [args for sql, args in operations if "INSERT INTO" in sql]
    assert len(inserts) == 1 and json.loads(inserts[0][1]) == {"engine": "another-case"}
