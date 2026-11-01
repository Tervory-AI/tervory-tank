"""The saved-source path stays free, without installing the researcher in Tank."""
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agents/market_lab"))
from core import http, research_adapter


@pytest.mark.asyncio
async def test_saved_feed_answer_never_calls_web_research(monkeypatch):
    tenant = "00000000-0000-0000-0000-0000000000aa"
    saved = {"content": "", "facts": [{"text": "Saved observation", "href": "/market-lab/source/record", "name": "Source"}], "sources": []}
    @asynccontextmanager
    async def ledger():
        yield object()
    async def answer(_ledger, owner, question, *, engine):
        assert owner == tenant and question == "saved question"
        return saved
    async def forbidden(*args):
        raise AssertionError("A saved answer must not invoke web research")
    monkeypatch.setattr(http, "answer", answer)
    monkeypatch.setattr(research_adapter, "research_web", forbidden)
    app = FastAPI()
    app.include_router(http.build_router(key_ok=lambda _: True, ledger_context=ledger))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://room") as client:
        response = await client.post("/market/ask", json={"tenant_id": tenant, "question": "saved question"})
    assert response.status_code == 200 and response.json() == saved
