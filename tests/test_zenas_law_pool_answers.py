"""Ask Zenas fills passages from the law pool when the caller sends none."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.zenas.core.service import _passages_from_pool, retrieve  # noqa: E402
from agents.zenas.pool.model import Chunk  # noqa: E402

TENANT = "00000000-0000-0000-0000-0000000000b2"

CHUNK = Chunk(
    chunk_id="c1",
    version_id="v1",
    document_id="d1",
    jurisdiction="us",
    path="141.1",
    heading="Entry",
    text="Merchandise must be entered at the port.",
    citation="19 C.F.R. § 141.1",
    citation_key="19-cfr-141.1",
    ordinal=0,
)


class _Pool:
    async def find_by_citation(self, citation: str, *, jurisdiction: str, as_at=None):
        if "141.1" in citation:
            return [CHUNK]
        return []

    async def search_text(self, query: str, *, jurisdiction: str, as_at=None, level=None, kind=None, limit=20):
        if "merchandise" in query.lower():
            return [CHUNK]
        return []


class _Tank:
    async def route(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("tank must not be called for pool-only retrieve")


@pytest.mark.asyncio
async def test_passages_from_pool_none_returns_empty() -> None:
    out = await _passages_from_pool(
        None,
        query="entry of merchandise",
        citation="",
        jurisdiction="us",
        as_at=None,
        level=None,
        kind=None,
    )
    assert out == []


@pytest.mark.asyncio
async def test_passages_from_pool_reads_search_text() -> None:
    out = await _passages_from_pool(
        _Pool(),
        query="merchandise entered",
        citation="",
        jurisdiction="us",
        as_at=None,
        level=None,
        kind=None,
    )
    assert len(out) == 1
    assert out[0]["citation"] == "19 C.F.R. § 141.1"
    assert "Merchandise" in out[0]["text"]


@pytest.mark.asyncio
async def test_retrieve_uses_pool_when_no_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _home(*_a, **_k):
        return SimpleNamespace(tenant_id=TENANT), None

    async def _gate(*_a, **_k):
        return {"stopped": False, "scope": {"criminal": False}}

    monkeypatch.setattr("agents.zenas.core.service._use_home", _home)
    monkeypatch.setattr("agents.zenas.core.service._gate", _gate)

    result = await retrieve(
        ladder=SimpleNamespace(),
        tank=_Tank(),
        tenant_id=TENANT,
        home_region="us-east",
        box_region="us-east",
        jurisdiction="us",
        query="merchandise entered at port",
        pool=_Pool(),
    )
    assert result.get("ok") is True
    assert result.get("passages")
    assert result["passages"][0]["doc_id"] == "d1"


@pytest.mark.asyncio
async def test_retrieve_empty_when_pool_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _home(*_a, **_k):
        return SimpleNamespace(tenant_id=TENANT), None

    async def _gate(*_a, **_k):
        return {"stopped": False, "scope": {"criminal": False}}

    monkeypatch.setattr("agents.zenas.core.service._use_home", _home)
    monkeypatch.setattr("agents.zenas.core.service._gate", _gate)

    result = await retrieve(
        ladder=SimpleNamespace(),
        tank=_Tank(),
        tenant_id=TENANT,
        home_region="us-east",
        box_region="us-east",
        jurisdiction="us",
        query="anything",
        pool=None,
    )
    assert result.get("ok") is True
    assert result.get("passages") == []


def test_app_source_wires_pool_store_not_unset_attr() -> None:
    """Regression: /answers and /ladder/retrieve must use _pool_store(), not app.state.law_pool."""
    src = (ROOT / "agents" / "zenas" / "app.py").read_text(encoding="utf-8")
    assert 'pool=getattr(app.state, "law_pool", None)' not in src
    assert "async with _pool_store() as law_pool:" in src
    # Empty-passage fill on /answers
    assert "if not passages:" in src
    assert 'query=body.question' in src
