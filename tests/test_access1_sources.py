"""Access fallback ordering, provenance, and existing-paid-route continuation."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location("base_access_sources", Path(__file__).resolve().parents[1] / "agents/base/access_sources.py")
sources = importlib.util.module_from_spec(spec); spec.loader.exec_module(sources)


@pytest.mark.asyncio
async def test_retry_backoff_then_dated_archive(monkeypatch):
    events = []
    async def run(): events.append("live"); return {"text": "", "error": "home page unreachable", "pages": [], "emails": []}
    async def sleep(value): events.append(value)
    async def post(url, **kwargs):
        events.append("archive")
        return SimpleNamespace(status_code=200, json=lambda: {"found": True, "html": "<p>Old business page</p>", "date": "20200101120000", "source": "Wayback Machine"})
    monkeypatch.setattr(sources.asyncio, "sleep", sleep)
    result = await sources.scrape_with_archives(run, SimpleNamespace(post=post), "http://tank", {}, "tenant", {"website": "https://public.example"})
    assert events == ["live", 1, "live", 3, "live", "archive"]
    assert result["archived"] and result["via"] == "archived, dated" and result["archive_date"] == "20200101120000"
    assert not result["emails"] and not result["pages"]


@pytest.mark.asyncio
async def test_captcha_never_uses_archive_as_bypass():
    async def run(): return {"text": "", "error": "blocked by human check"}
    async def post(*args, **kwargs): raise AssertionError("A human check must stay in the human queue")
    result = await sources.scrape_with_archives(run, SimpleNamespace(post=post), "http://tank", {}, "tenant", {"website": "https://public.example"})
    assert result["error"] == "blocked by human check"


@pytest.mark.asyncio
async def test_exhausted_archives_leave_existing_paid_ladder(monkeypatch):
    async def run(): return {"text": "", "error": "home page unreachable"}
    async def sleep(value): pass
    async def post(*args, **kwargs): return SimpleNamespace(status_code=200, json=lambda: {"found": False, "next": "existing_paid_rung"})
    monkeypatch.setattr(sources.asyncio, "sleep", sleep)
    result = await sources.scrape_with_archives(run, SimpleNamespace(post=post), "http://tank", {}, "tenant", {"website": "https://public.example"})
    assert result["access_sources"]["next"] == "existing_paid_rung"
    assert "paid" not in json.dumps(result).replace("existing_paid_rung", "")
