"""A changed store page must say it can't read, and must not guess a price."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
sys.path.insert(0, str(ROOT / "agents" / "tiger"))
sys.path.insert(0, str(ROOT / "tests"))

from tiger_alert_page.mutate import changed  # noqa: E402
from tiger_alert_page.score import (  # noqa: E402
    COST_TARGET_USD,
    PAGE_MEAN_MS,
    _learn_bases,
    _load_extract,
    _rows,
    score_pages,
)
from watch import DomainLimiter, MemoryStore, run_check  # noqa: E402

TENANT = "11111111-1111-1111-1111-111111111111"


def _reports():
    extract = _load_extract()
    bases = _learn_bases(extract)
    changed_pages = score_pages(_rows("page_changed.jsonl"), bases, extract)
    controls = score_pages(_rows("page_controls.jsonl"), bases, extract)
    traps = score_pages(_rows("page_traps.jsonl"), bases, extract)
    return changed_pages, controls, traps


def test_changed_pages_never_guess() -> None:
    changed_pages, controls, traps = _reports()
    for split in ("build", "heldout"):
        summary = changed_pages["summary"][split]
        assert summary["n"] > 0
        assert summary["ok_pct"] == 100
        assert summary["guesses"] == 0
    assert controls["summary"]["control"]["ok_pct"] == 100
    assert all(row["pass"] for row in traps["rows"])
    assert changed_pages["cost_usd"] == COST_TARGET_USD
    assert changed_pages["mean_ms"] <= PAGE_MEAN_MS
    assert all(row["verified"] == "no" for row in changed_pages["rows"])


def test_a_watch_does_not_guess_after_the_layout_changes() -> None:
    extract = _load_extract()
    original = (ROOT / "tests" / "tiger_alert_page" / "fixtures" / "known" / "sale.html").read_text(encoding="utf-8")
    learned = extract.extract(original, "https://example.test/item")
    from page_guard import learn_layout

    signature = learn_layout(original, learned)
    broken = changed(original, signature, "strip")
    store = MemoryStore()
    watch = {
        "id": "watch-1",
        "tenant_id": TENANT,
        "url": "https://example.test/item",
        "label": "sample",
        "engine": "core",
        "every": "1h",
        "enabled": True,
        "threshold": "0",
    }
    pages = {"html": original}

    async def render(url: str, session: str, agent: str, tenant: str) -> dict:
        return {"ok": True, "challenge": False, "html": pages["html"], "png_base64": None}

    async def extract_html(html: str, url: str) -> dict:
        return extract.extract(html, url)

    async def ocr(png: str, url: str) -> dict:
        raise AssertionError("a changed page must not be guessed from a screenshot")

    async def fetch_text(url: str) -> str:
        return ""

    tick = {"n": 0}

    def clock() -> datetime:
        tick["n"] += 1
        return datetime(2026, 10, 16, tzinfo=timezone.utc) + timedelta(seconds=tick["n"])

    async def check() -> None:
        await store.create_watch(watch)
        first = await run_check(
            store, TENANT, watch, "tiger", render, extract_html, ocr, fetch_text, DomainLimiter(0), now=clock,
        )
        assert first["status"] == "observed"
        assert first["price"] == "9.99"
        assert first["alerts"] == []
        pages["html"] = broken
        second = await run_check(
            store, TENANT, watch, "tiger", render, extract_html, ocr, fetch_text, DomainLimiter(0), now=clock,
        )
        assert second["status"] == "can't read"
        assert second["price"] is None
        assert second["alerts"] == []
        assert "1.11" not in str(second["observation"]["price"])
        pages["html"] = original.replace("9.99", "8.49")
        third = await run_check(
            store, TENANT, watch, "tiger", render, extract_html, ocr, fetch_text, DomainLimiter(0), now=clock,
        )
        assert third["status"] == "observed"
        assert third["price"] == "8.49"
        assert {row["kind"] for row in third["alerts"]} == {"price"}

    asyncio.run(check())
