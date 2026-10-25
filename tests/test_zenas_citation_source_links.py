"""Source metadata checks using the repository's saved official Delaware statute.

This statute is not presented as an answer to the founder's forum-selection
question. Live answer/link verification remains a separate acceptance check.
"""

from datetime import date
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

from agents.zenas.core.citation_sources import cited_sources, public_source_url
from agents.zenas.core.engine import cite_check
from agents.zenas.core.law_pool import AsyncpgLawPool
from agents.zenas.core.service import _passages_from_pool
from agents.zenas.pool.adapters.states import DelawareAdapter
from agents.zenas.pool.catalogue import sources_for_region
from agents.zenas.pool.chunk import chunk_document
from agents.zenas.pool.store import PostgresStore

ROOT = Path(__file__).resolve().parents[1]


def official_document():
    source = next(row for row in sources_for_region("us-east") if row.source_id == "delaware-code")
    raw = (ROOT / "agents/zenas/pool/fixtures/saved/delaware-code/title8-c001-sc01.html").read_bytes()
    document = next(row for row in DelawareAdapter().parse(raw, source) if row.citation == "8 Del. C. § 101")
    return source, document


def test_link_comes_from_the_quote_checked_document_version():
    _, document = official_document()
    chunk = chunk_document(document)[0]
    passage = {"doc_id": document.id, "version_id": document.version_id, "citation": document.citation,
               "url": document.url, "text": chunk.text, "status": document.status}
    statements = [{"citation": document.citation, "quote": chunk.text}]
    checked = cite_check(statements, [passage])
    assert checked["passed"]
    assert cited_sources(statements, checked, [passage], [document.citation], require_links=True) == [
        {"citation": document.citation, "quote": chunk.text, "url": document.url}]
    assert cited_sources(statements, checked, [{**passage, "url": ""}], [document.citation], require_links=True) is None
    assert cited_sources(statements, checked, [{**passage, "version_id": ""}], [document.citation], require_links=True) is None


@pytest.mark.parametrize("value", [None, "", "http://delcode.delaware.gov/title8/c001/sc01/index.html", "https://localhost/", "https://127.0.0.1/", "https://example.com/", "https://law.test/", "https://delcode.delaware.gov/?api_key="])
def test_nonpublic_or_credential_source_links_are_not_returned(value):
    assert public_source_url(value) == ""


@pytest.mark.asyncio
async def test_real_postgres_passages_keep_the_stored_source_url():
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    admin = _admin_url()
    name = "zenas_sources_" + uuid4().hex
    await _create_database(admin, name)
    pool = await asyncpg.create_pool(_database_url(admin, name))
    try:
        source, document = official_document()
        async with pool.acquire() as conn:
            store = PostgresStore(conn, home_region="us-east")
            await store.apply_schema()
            await store.record_source(source)
            await store.upsert_version(document, chunk_document(document), on=date.today())
        law = AsyncpgLawPool(pool, home_region="us-east")
        passages = await _passages_from_pool(law, query="", citation=document.citation, jurisdiction="us", as_at=None, level=None, kind=None)
        assert passages
        assert all(row["url"] == document.url and row["title"] == document.title for row in passages)
        assert law.requires_source_links
        chunks = await law.find_by_citation(document.citation, jurisdiction="us")
        assert await law.source_metadata(chunks, jurisdiction="za") == {}
        assert await AsyncpgLawPool(pool, home_region="za").source_metadata(chunks, jurisdiction="us") == {}
    finally:
        await pool.close()
        await _drop_database(admin, name)
