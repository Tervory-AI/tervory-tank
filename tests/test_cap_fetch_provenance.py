"""Actual CAP fetch→text payload→parser/ingest path; offline archive responses only."""
import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from agents.zenas.pool.adapters.cases import CapAdapter, CourtListenerAdapter
from agents.zenas.pool.blobs import text_payloads
from agents.zenas.pool.catalogue import CATALOGUE
from agents.zenas.pool.ingest import ingest_snapshot
from agents.zenas.pool.store import MemoryStore
from agents.zenas.pool.region import RegionError

SOURCE = next(s for s in CATALOGUE if s.source_id == "cap")
RAW = (Path(__file__).parents[1] / "agents/zenas/pool/fixtures/saved/cap/f2d-1-0001-01.json").read_bytes()
URL = "https://static.case.law/f2d/1/cases/0001-01.json"
INDEX = b'<a href="0001-01.json">case</a>'


async def fetched(raw=RAW, index=INDEX, *, fail=False):
    calls = []
    async def get(url, headers):
        calls.append(url)
        if url.endswith("/cases/"): return index
        if fail: raise OSError("offline fetch failure")
        return raw
    return await CapAdapter().fetch(get), calls


@pytest.mark.asyncio
async def test_successful_machine_source_url_survives_real_ingest_without_altering_archive_or_version():
    blobs, calls = await fetched()
    assert calls == ["https://static.case.law/f2d/1/cases/", URL]
    assert bytes(blobs[0]) == RAW and hashlib.sha256(blobs[0]).digest() == hashlib.sha256(RAW).digest()
    assert json.loads(blobs[0]) == json.loads(RAW) and "frontend_url" not in json.loads(blobs[0])
    payload = text_payloads(blobs[0])[0]
    plain = CapAdapter().parse(RAW, SOURCE)[0]
    document = CapAdapter().parse(payload, SOURCE)[0]
    assert document.url == URL and plain.url == ""
    assert (document.text, document.content_hash, document.version_id) == (plain.text, plain.content_hash, plain.version_id)
    store = MemoryStore(home_region="us-east")
    assert await ingest_snapshot(store, SOURCE, blobs, on=date(2026, 11, 1), region="us-east") == 1
    stored = list(store.docs.values())[0]
    assert stored.url == URL and stored.content_hash == plain.content_hash


@pytest.mark.asyncio
async def test_declared_frontend_and_other_adapter_behavior_remain_unchanged():
    row = json.loads(RAW); row["frontend_url"] = "https://example.org/published-case"
    blobs, _ = await fetched(json.dumps(row).encode())
    assert CapAdapter().parse(blobs[0], SOURCE)[0].url == row["frontend_url"]
    courtlistener = next(s for s in CATALOGUE if s.source_id == "courtlistener")
    raw_blobs, _ = await fetched()
    assert CourtListenerAdapter().parse(raw_blobs[0], courtlistener)[0].url == ""


@pytest.mark.asyncio
async def test_old_records_do_not_inherit_prior_fetch_or_guessed_urls_and_region_gate_still_runs():
    blobs, _ = await fetched()
    adapter = CapAdapter()
    assert adapter.parse(blobs[0], SOURCE)[0].url == URL
    assert adapter.parse(RAW, SOURCE)[0].url == ""
    with pytest.raises(RegionError, match="belongs to us-east"):
        await ingest_snapshot(MemoryStore(home_region="za"), SOURCE, blobs, on=date(2026, 11, 1), region="za")


@pytest.mark.asyncio
async def test_failure_or_malformed_archive_never_produces_a_guessed_document():
    with pytest.raises(OSError): await fetched(fail=True)
    blobs, _ = await fetched(b"not-json")
    with pytest.raises(json.JSONDecodeError): CapAdapter().parse(blobs[0], SOURCE)
    assert CapAdapter().parse(RAW, SOURCE)[0].url == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["https://evil.example/static.case.law/a.json", "https://static.case.law.evil.example/a.json",
    "https://static.case.law@evil.example/a.json", "http://static.case.law/a.json", "https://static.case.law:444/a.json"])
async def test_non_archive_or_credentialed_urls_are_never_fetched_or_used_as_provenance(url):
    blobs, calls = await fetched(index=f'<a href="{url}">case</a>'.encode())
    assert blobs == [] and calls == ["https://static.case.law/f2d/1/cases/"]


@pytest.mark.asyncio
async def test_future_fetch_does_not_rewrite_an_existing_unchanged_version():
    store = MemoryStore(home_region="us-east")
    assert await ingest_snapshot(store, SOURCE, [RAW], on=date(2026, 11, 1), region="us-east") == 1
    before = next(iter(store.docs.values()))
    original_version = before.version_id
    blobs, _ = await fetched()
    assert await ingest_snapshot(store, SOURCE, blobs, on=date(2026, 11, 1), region="us-east") == 0
    assert len(store.docs) == 1
    assert next(iter(store.docs.values())).version_id == original_version
    assert next(iter(store.docs.values())).url == ""  # Explicit repair remains a separate reviewed operation.
