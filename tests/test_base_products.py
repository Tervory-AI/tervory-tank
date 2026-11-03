"""Offline products: structured page evidence only, never page instructions."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest
import skala

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "tank/skills/base.extract/2.0.1"
NEW = OLD.with_name("2.1.0")
sys.path.insert(0, str(ROOT / "agents/base"))
from pipeline import enrich_one  # noqa: E402


def load(path):
    spec = importlib.util.spec_from_file_location("placeholder_extract", path / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_preserved_cases_fixtures_and_candidate_evals():
    assert (NEW / "evals/cases.jsonl").read_bytes().startswith((OLD / "evals/cases.jsonl").read_bytes())
    for path in (OLD / "evals/fixtures").iterdir():
        assert (NEW / "evals/fixtures" / path.name).read_bytes() == path.read_bytes()
    module = load(NEW)
    cases = [json.loads(line) for line in (NEW / "evals/cases.jsonl").read_text().splitlines()]
    for case in cases:
        output = await module.run(case["input"], None)
        assert skala.score_case(case["expected"], output, case.get("tolerance", "exact"))[0], case["name"]


@pytest.mark.asyncio
async def test_old_version_ignores_pages_and_prose_never_makes_products():
    old, new = load(OLD), load(NEW)
    payload = {"name": "placeholder", "text": "placeholder sells a widget for $10 USD " * 3}
    pages = [{"source_url": "https://placeholder.example", "checked_at": "2026-11-03", "html": '<script type="application/ld+json">{"@type":"Product","name":"placeholder"}</script>'}]
    assert await old.run(payload, None) == await old.run({**payload, "pages": pages}, None)
    assert (await new.run(payload, None))["products"] == []


@pytest.mark.asyncio
async def test_provenance_limits_and_decimal_precision():
    module = load(NEW)
    products = [{"@type": "Product", "name": "placeholder " + str(i) + "x" * 210,
                 "offers": {"@type": "Offer", "price": "01.9900", "priceCurrency": "USD"}} for i in range(60)]
    pages = [{"source_url": "https://placeholder.example/list", "checked_at": "2026-11-03",
              "html": '<script type="application/ld+json">' + json.dumps(products) + '</script>'}]
    result = (await module.run({"pages": pages}, None))["products"]
    assert len(result) == 50
    for row in result:
        assert len(row["name"]) == 200
        assert row["price"] == "01.9900" and row["currency"] == "USD"
        assert row["source_url"] == pages[0]["source_url"] and row["checked_at"] == pages[0]["checked_at"]
    pages[0]["html"] = '<script type="application/ld+json">{"@type":"Product","name":"placeholder","offers":{"price":12.900}}</script>'
    row = (await module.run({"pages": pages}, None))["products"][0]
    assert row["price"] == "12.900" and row["currency"] == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("has_products", [False, True])
async def test_pipeline_forwards_existing_pages_and_retains_only_returned_products(has_products):
    page = {"source_url": "https://placeholder.example", "checked_at": "2026-11-03", "html": "<p>placeholder</p>"}
    product = {"name": "placeholder", "source_url": page["source_url"], "checked_at": page["checked_at"]}
    async def call(skill, payload):
        if skill == "base.find_site":
            return {"website": {"value": page["source_url"], "confidence": 90}}
        if skill == "base.scrape_site":
            return {"text": "placeholder " * 10, "page_responses": [page]}
        if skill == "base.extract":
            assert payload["pages"] == [page]
            return {"confidence": 90, **({"products": [product]} if has_products else {})}
        return {}
    outcome = await enrich_one({"name": "placeholder"}, None, [], None, call)
    assert outcome.status == "done", outcome.error
    if has_products:
        assert outcome.profile["products"] == {"value": [product], "source": "site:code", "confidence": 90}
    else:
        assert "products" not in outcome.profile


@pytest.mark.asyncio
async def test_search_card_reuses_summary_for_products_and_preserves_older_records(monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4
    from fastapi import FastAPI
    import command

    product = {"name": "placeholder", "source_url": "https://placeholder.example/product", "checked_at": "2026-11-03"}
    older = {"profile": {"name": {"value": "placeholder older"}}}
    app = FastAPI()
    @app.get("/v1/base/records")
    async def records():
        return [{"profile": {"products": {"value": [product]}}}, older]
    monkeypatch.setitem(sys.modules, "main", SimpleNamespace(app=app, TANK_API_KEY="placeholder", box_region=lambda: "us-east"))
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "placeholder-founder")
    actor = command.Actor(uuid4(), "placeholder-founder", True)
    status, result = await command.dispatch_action(command.PlannedAction(tool="base.search", arguments={}), actor)
    assert status == 200 and json.loads(result[0]["summary"]) == [product]
    assert result[1] == older


@pytest.mark.asyncio
async def test_microdata_offer_and_each_pages_own_provenance():
    pages = [
        {"source_url": "https://placeholder.example/first", "checked_at": "2026-11-01",
         "html": '<div itemscope itemtype="https://schema.org/Product"><span itemprop="name">placeholder first</span><div itemprop="offers" itemscope itemtype="https://schema.org/Offer"><meta itemprop="price" content="9.00"><meta itemprop="priceCurrency" content="EUR"></div></div>'},
        {"source_url": "https://placeholder.example/second", "checked_at": "2026-11-02",
         "html": '<script type="application/ld+json">{"@type":"ListItem","item":"https://placeholder.example/product"}</script>'},
    ]
    result = (await load(NEW).run({"pages": pages}, None))["products"]
    assert len(result) == 2
    assert result[0]["price"] == "9.00" and result[0]["currency"] == "EUR"
    assert result[1]["name"] == "" and result[1]["url"] == "https://placeholder.example/product"
    for row, page in zip(result, pages):
        assert row["source_url"] == page["source_url"] and row["checked_at"] == page["checked_at"]
