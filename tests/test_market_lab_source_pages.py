"""Sorted source pages keep original evidence indexes and exact numeric values."""
import copy
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/market_lab"))
from core.evidence import document, document_page, number_label, save_check
from core.ledger import MemoryLedger

OWNER = "00000000-0000-0000-0000-000000000001"
OTHER = "00000000-0000-0000-0000-000000000002"


@pytest.mark.parametrize("raw,expected", [
    ("14474", "14,474"), ("9000.50", "9,000.5"), ("-14474.2500", "-14,474.25"),
    ("12345678901234567890123", "12,345,678,901,234,567,890,123"), ("0", "0"),
    ("0.0001", "0.0001"), ("1E+6", "1,000,000"),
])
def test_values_use_grouping_without_float_rounding(raw, expected):
    assert number_label(raw) == expected


@pytest.mark.asyncio
async def test_pages_are_newest_first_and_citations_keep_immutable_indexes():
    ledger = MemoryLedger()
    ledger.pool.batches["saved"] = {"tenant_id": OWNER, "status": "pooled"}
    points = [{"series_id": "volume", "batch_id": "saved", "title": "Container volume",
               "date": f"{1960 + index // 12}-{index % 12 + 1:02d}-01", "value": str(14474 + index),
               "unit": "TEU", "geo": "US", "geo_level": "national", "frequency": "monthly", "revision": "v1"}
              for index in range(123)]
    result = {"source_id": "source", "name": "Container volumes", "points": points,
              "events": [], "fixture": True, "note": ""}
    check = await save_check(ledger, OWNER, result, at=datetime.now(timezone.utc))
    ident = check["document_id"]
    original = copy.deepcopy(await document(ledger, OWNER, ident, fixtures=True))
    pages = [await document_page(ledger, OWNER, ident, offset, fixtures=True) for offset in (0, 50, 100)]
    assert [len(page["points"]) for page in pages] == [50, 50, 23]
    assert all(page["page_size"] == 50 and page["point_count"] == 123 for page in pages)
    rows = [point for page in pages for point in page["points"]]
    assert [point["index"] for point in rows] == list(reversed(range(123)))
    assert rows[-1]["display_value"] == "14,474"
    assert rows[-1]["value"] == "14474"
    for index in (0, 22, 23, 72, 73, 122):
        focused = await document_page(ledger, OWNER, ident, row=index, fixtures=True)
        assert focused["offset"] == ((122 - index) // 50) * 50
        point = next(point for point in focused["points"] if point["index"] == index)
        assert point["value"] == original["points"][index]["value"]
    assert await document_page(ledger, OWNER, ident, 999999, fixtures=True) == pages[-1]
    assert await document_page(ledger, OWNER, ident, 0, fixtures=True) == pages[0]
    assert await document_page(ledger, OTHER, ident, row=0, fixtures=True) is None
    assert await document(ledger, OWNER, ident, fixtures=True) == original


@pytest.mark.asyncio
async def test_notice_citations_also_keep_their_original_indexes():
    ledger = MemoryLedger()
    events = [{"date": f"{1960 + index}-01-01", "title": "Notice", "body": "Saved notice",
               "geo": "US", "kind": "notice", "url": "https://publisher.test/notice"} for index in range(67)]
    check = await save_check(ledger, OWNER, {"source_id": "notices", "name": "Notices", "points": [],
        "events": events, "fixture": True, "note": ""}, at=datetime.now(timezone.utc))
    page = await document_page(ledger, OWNER, check["document_id"], fixtures=True)
    assert len(page["events"]) == 50 and page["events"][0]["index"] == 66
    earlier = await document_page(ledger, OWNER, check["document_id"], row=0, fixtures=True)
    assert earlier["offset"] == 50 and earlier["events"][-1]["index"] == 0


@pytest.mark.asyncio
async def test_mixed_document_focuses_the_cited_kind_and_answer_marks_notices():
    from core.evidence import answer
    from fixture_proof.mixed_source import seed_mixed_source
    ledger = MemoryLedger()
    ident = await seed_mixed_source(ledger, OWNER, fixtures=True)
    for kind, index, offset in [("event", 5, 50), ("event", 59, 0), ("point", 0, 100), ("point", 122, 0)]:
        page = await document_page(ledger, OWNER, ident, row=index, row_kind=kind, fixtures=True)
        assert page["point_count"] == 123 and page["event_count"] == 60
        assert page["offset"] == offset
        assert index in [row["index"] for row in page["events" if kind == "event" else "points"]]
        assert await document_page(ledger, OTHER, ident, row=index, row_kind=kind, fixtures=True) is None
    for index in (5, 59):
        response = await answer(ledger, OWNER, f"Harbor notice {1960 + index}", fixtures=True)
        assert len(response["facts"]) == 1
        assert response["facts"][0]["href"] == f"/market-lab/sources/{ident}?row={index}&kind=event#event-{index}"
