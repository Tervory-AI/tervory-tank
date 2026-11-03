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
