"""zenas.retrieve — code only. The pool first. SAFLII for a saved or live ZA case."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _engine() -> Any:
    import sys

    sys.dont_write_bytecode = True
    path = Path(__file__).resolve().parents[2] / "zenas.shared" / "engine.py"
    spec = importlib.util.spec_from_file_location("zenas_shared_engine_retrieve_110", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("ladder engine is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _search_and_fetch() -> Any:
    import sys

    root = Path(__file__).resolve().parents[4]
    adapter = root / "agents" / "zenas" / "pool" / "adapters" / "za_saflii.py"
    if not adapter.is_file():
        return None
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from agents.zenas.pool.adapters.za_saflii import search_and_fetch

    return search_and_fetch


def _as_passage(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": str(item.get("doc_id") or ""),
        "version_id": str(item.get("version_id") or ""),
        "citation": str(item.get("citation") or ""),
        "heading": str(item.get("title") or item.get("heading") or ""),
        "text": str(item.get("excerpt") or item.get("text") or ""),
        "path": "",
        "jurisdiction": "za",
        "kind": "case",
        "level": "national",
        "status": "published",
        "url": str(item.get("url") or ""),
    }


def _merge(passages: list[dict[str, Any]], excerpts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = list(passages)
    seen = {str(item.get("citation") or "") for item in passages}
    for item in excerpts:
        passage = _as_passage(item)
        citation = passage["citation"]
        if citation and citation in seen:
            continue
        if citation:
            seen.add(citation)
        merged.append(passage)
    return merged


async def _from_saved_pages(body: dict[str, Any], search_and_fetch: Any) -> dict[str, Any]:
    pages = {str(url): str(html) for url, html in (body.get("saflii_pages") or {}).items()}
    hits = [str(url) for url in (body.get("saflii_hits") or list(pages))]
    cgi = str(body.get("saflii_cgi") or "")

    async def search(_query: str) -> list[str]:
        return hits

    async def http_get(url: str, headers: dict[str, str]) -> bytes:
        del headers
        if "sinosrch-adw.cgi" in url:
            return cgi.encode("utf-8")
        return pages.get(url, "").encode("utf-8")

    query = str(body.get("query") or body.get("citation") or "saflii")
    return await search_and_fetch(query, search=search, http_get=http_get, live=False)


async def _saflii(body: dict[str, Any], ctx: Any) -> dict[str, Any] | None:
    saved = body.get("saflii_pages") or body.get("saflii_hits") or body.get("saflii_cgi")
    kind = str(body.get("kind") or "")
    if not saved:
        if str(body.get("jurisdiction") or "") != "za" or kind != "case":
            return None
        # A room without SearXNG still searches. The adapter uses a public
        # web search, then SAFLII's own search, and fetches through Chrome.
    search_and_fetch = _search_and_fetch()
    if search_and_fetch is None:
        return {"state": "unavailable", "reason": "SAFLII adapter is not on this image.", "excerpts": []}
    if saved:
        return await _from_saved_pages(body, search_and_fetch)
    return await search_and_fetch(str(body.get("query") or body.get("citation") or ""), live=True)


async def run(payload: dict, ctx: Any) -> dict:
    engine = _engine()
    body = payload or {}
    passages = engine.retrieve_passages(
        list(body.get("corpus") or []),
        query=str(body.get("query") or ""),
        citation=str(body.get("citation") or ""),
        jurisdiction=str(body.get("jurisdiction") or ""),
        as_at=body.get("as_at"),
        level=body.get("level"),
        kind=body.get("kind"),
    )
    saflii = await _saflii(body, ctx)
    if saflii is None:
        return {
            "count": len(passages),
            "citations": [item["citation"] for item in passages],
            "passages": passages,
        }
    merged = _merge(passages, list(saflii.get("excerpts") or []))
    return {
        "count": len(merged),
        "citations": [item["citation"] for item in merged],
        "passages": merged,
        "saflii_state": str(saflii.get("state") or ""),
    }
