"""Recorded-page signals, optional approval gate and legacy CSV compatibility."""
from __future__ import annotations

import copy
import csv
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/base"))
from pipeline import BASE_CORE, OPTIONAL_SKILLS, enrich_one
from room import SkillClient, SkillError
from base_evidence import row_fields
from base_metrics import csv_text, export_records
from base_product_fixtures import finished, raw
from agents.base.engines.ffl import reference

PKG = ROOT / "tank/skills/base.site_signals/1.0.0"
AT = "2026-11-01T12:00:00+00:00"
SITE = "https://recorded.example/"


def load(path):
    spec = importlib.util.spec_from_file_location("b2_" + str(path).replace("/", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Offline:
    def __getattr__(self, name):
        raise AssertionError(f"No network or model access allowed: {name}")


async def signals(html, **kwargs):
    return await load(PKG / "run.py").run({"website": SITE, "as_of": "2026-11-01",
        "page_responses": [{"html": html, "source_url": SITE, "checked_at": AT, "headers": kwargs.pop("headers", {})}], **kwargs}, Offline())


@pytest.mark.asyncio
@pytest.mark.parametrize("approved", [None, "1.0.0"])
@pytest.mark.parametrize("preview", [False, True])
async def test_optional_pinning_uses_approved_only(approved, preview, monkeypatch):
    client = SkillClient(None, "http://tank", "")
    seen = []
    async def describe(skill, requested_preview):
        seen.append((skill, requested_preview))
        if skill == "base.site_signals" and approved is None:
            raise SkillError("no approved version", 409)
        return {"version": approved if skill == "base.site_signals" else "1.0.0"}
    monkeypatch.setattr(client, "describe", describe)
    versions, refs = await client.pin(preview, None)
    assert "base.site_signals" not in BASE_CORE
    assert "base.site_signals" in OPTIONAL_SKILLS
    assert ("base.site_signals" in versions) == bool(approved)
    assert seen[-1] == ("base.site_signals", False)
    assert set(versions) == set(BASE_CORE) | ({"base.site_signals"} if approved else set())
    assert (refs.get("base.site_signals") == "base.site_signals@1.0.0") == bool(approved)


@pytest.mark.asyncio
async def test_optional_pinning_does_not_swallow_outages(monkeypatch):
    client = SkillClient(None, "http://tank", "")
    async def describe(skill, preview):
        if skill == "base.site_signals":
            raise SkillError("unavailable", 502)
        return {"version": "1.0.0"}
    monkeypatch.setattr(client, "describe", describe)
    with pytest.raises(SkillError):
        await client.pin(False, None)


async def pipeline_run(refs):
    seen = []
    result = await signals('<meta name="generator" content="WordPress 6.8"><button>Add to cart</button><footer>Copyright 2026 Recorded</footer>')
    async def call(skill, payload):
        seen.append((skill, payload))
        return {"base.normalize": {"fields": {"name": {"value": "Recorded business", "confidence": 90}}},
            "base.find_site": {"website": {"value": SITE, "confidence": 90}},
            "base.scrape_site": {"html": "Recorded", "text": "Recorded", "pages": [SITE]},
            "base.site_signals": result,
            "base.verify": {"confidence": 60, "tier": "use_with_awareness"}}.get(skill, {})
    out = await enrich_one({"name": "Recorded business"}, None, [], None, call, refs)
    assert out.status == "done", out.error
    return out, seen


@pytest.mark.asyncio
async def test_unapproved_optional_pass_leaves_pipeline_exactly_unchanged():
    baseline, first = await pipeline_run(None)
    unapproved, second = await pipeline_run({})
    assert baseline == unapproved
    assert first == second
    assert "base.site_signals" not in [skill for skill, payload in second]
    assert "2b_signals" not in unapproved.passes
    assert "technologies" not in unapproved.profile


@pytest.mark.asyncio
async def test_approved_pass_runs_after_scrape_and_reaches_verify_and_export():
    out, seen = await pipeline_run({"base.site_signals": "base.site_signals@1.0.0"})
    names = [skill for skill, payload in seen]
    assert names.index("base.site_signals") == names.index("base.scrape_site") + 1
    verify = next(payload for skill, payload in seen if skill == "base.verify")
    assert verify["profile"]["sells_online"]["value"] is True
    assert out.profile["technologies"]["value"][0]["name"] == "WordPress"
    row = {"status": "done", "profile": out.profile, "passes": out.passes}
    fields = row_fields(row)
    for name in ("technologies", "sells_online", "site_newest_year"):
        assert fields[name]["verified"] is True
        assert fields[name]["source_url"] == SITE
        assert fields[name]["checked_at"] == AT
        assert fields[name]["evidence"][0]["text"]


@pytest.mark.asyncio
async def test_fingerprints_and_booking_quote_actions_have_evidence():
    out = await signals('''<html><head><meta name="generator" content="WordPress 6.8">
      <script src="https://www.googletagmanager.com/gtag/js?id=G-RECORDED"></script>
      <script src="https://js.stripe.com/v3/"></script></head><body>
      <a href="https://calendar.example/recorded">Book an appointment</a>
      <a href="https://quote.example/recorded">Request a quote</a></body></html>''')
    items = out["fields"]["technologies"]["value"]
    names = {item["name"] for item in items}
    assert {"WordPress", "Google Analytics", "Stripe", "https://calendar.example/recorded", "https://quote.example/recorded"} <= names
    assert all(item["evidence"] and item["confidence"] > 0 for item in items)
    assert "sells_online" not in out["fields"]  # Widgets alone do not establish a purchase path.
    assert (await signals("<p>Our article mentions WordPress, Shopify and Stripe.</p>"))["fields"] == {}


@pytest.mark.asyncio
async def test_shopify_action_and_conflicting_sales_statement():
    out = await signals('<script src="https://cdn.shopify.com/s/assets.js"></script><button>Buy now</button>')
    assert any(t["name"] == "Shopify" for t in out["fields"]["technologies"]["value"])
    assert out["fields"]["sells_online"]["value"] is True
    conflict = await signals('<button>Buy now</button><p>We do not sell online</p>')
    assert conflict["fields"]["sells_online"]["value"] is None


@pytest.mark.asyncio
async def test_newest_dates_ignore_future_and_non_article_dates():
    out = await signals('''<footer>Copyright 2019–2026 Recorded</footer>
      <time datetime="2026-10-31">Next event</time>
      <article><time datetime="2025-01-02">News</time><time datetime="2099-01-01">Future</time></article>
      <script type="application/ld+json">{"@type":"BlogPosting","datePublished":"2026-08-09"}</script>''',
      headers={"Last-Modified": "Wed, 15 Jan 2025 12:00:00 GMT"})
    fresh = out["fields"]["site_freshness"]["value"]
    assert fresh["copyright_year"]["value"] == 2026
    assert fresh["newest_post"]["value"] == "2026-08-09"
    assert fresh["last_modified"]["value"] == "2025-01-15"


@pytest.mark.asyncio
async def test_recorded_evals_exact_and_fixture_inputs_match():
    run = load(PKG / "run.py").run
    cases = [json.loads(line) for line in (PKG / "evals/cases.jsonl").read_text().splitlines()]
    assert len(cases) >= 5
    for case in cases:
        assert (PKG / "evals" / case["fixture"]).read_text() == case["input"]["page_responses"][0]["html"]
        assert await run(case["input"], Offline()) == case["expected"], case["name"]


@pytest.mark.asyncio
async def test_scrape_retains_safe_headers_from_same_requests():
    requested = []
    async def get(url, **kwargs):
        requested.append(url)
        return SimpleNamespace(status_code=200, url=url, text='<html><body>' + 'Recorded business. ' * 40 + '</body></html>',
            headers={"content-type": "text/html", "last-modified": "Wed, 15 Jan 2025 12:00:00 GMT", "x-powered-by": "Recorded", "set-cookie": "DO-NOT-RETAIN"})
    payload = {"website": SITE}
    new = await load(ROOT / "tank/skills/base.scrape_site/1.3.0/run.py").run(payload, SimpleNamespace(http=SimpleNamespace(get=get), env={}))
    assert requested == [SITE]
    assert new["page_responses"][0]["headers"] == {"content-type": "text/html", "last-modified": "Wed, 15 Jan 2025 12:00:00 GMT", "x-powered-by": "Recorded"}
    assert new["page_responses"][0]["checked_at"]
    old = await load(ROOT / "tank/skills/base.scrape_site/1.2.1/run.py").run(payload, SimpleNamespace(http=SimpleNamespace(get=get), env={}))
    assert {key: new[key] for key in old} == old


@pytest.mark.asyncio
async def test_false_sales_verifies_but_archived_or_undated_signals_do_not():
    out = await signals("<p>We do not sell online</p>")
    row = {"profile": out["fields"], "passes": {"2b_signals": {"skill": "base.site_signals@1.0.0"}}}
    assert row_fields(row)["sells_online"]["verified"] is True
    assert row_fields(row)["sells_online"]["value"] is False
    row["profile"]["sells_online"]["checked_at"] = None
    assert row_fields(row)["sells_online"]["verified"] is False
    row["passes"]["2b"] = {"archive_date": "2020-01-01"}
    assert "sells_online" not in row_fields(row)


@pytest.mark.asyncio
async def test_legacy_csv_bytes_remain_identical_with_signals_appended():
    row = finished(reference.project(raw()))
    row["fields"] = row_fields(row)
    before = export_records([row])
    out = await signals('<button>Add to cart</button><footer>Copyright 2026 Recorded</footer>')
    enriched = copy.deepcopy(row)
    enriched["profile"].update(out["fields"])
    enriched["passes"]["2b_signals"] = {"skill": "base.site_signals@1.0.0"}
    enriched["fields"] = row_fields(enriched)
    after = export_records([enriched])
    legacy = (PKG / "evals/fixtures/legacy.csv").read_bytes().decode("utf-8")
    legacy_columns = next(csv.reader(io.StringIO(legacy.lstrip("\ufeff"))))
    for exported in (before, after):
        parsed = list(csv.DictReader(io.StringIO(exported.lstrip("\ufeff"))))
        assert csv_text(parsed, legacy_columns).encode() == legacy.encode()
    exported = list(csv.DictReader(io.StringIO(after.lstrip("\ufeff"))))[0]
    assert exported["sells_online"] == "True"
    assert exported["site_newest_year"] == "2026"
    assert exported["sells_online_source_url"] == SITE
    assert json.loads(exported["sells_online_evidence"])[0]["text"] == "<button>Add to cart</button>"
