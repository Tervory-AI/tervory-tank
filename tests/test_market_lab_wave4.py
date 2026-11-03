"""Wave 4 code-only contracts with placeholder data and no external services."""
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agents/market_lab'))
from core.brief_sources import claims
from core.evidence import document_page
from core.jobs import perform_opportunities
from core.ledger import MemoryLedger
from engines.ffl.engine import plan

OWNER, OTHER = str(uuid4()), str(uuid4())
NOW = datetime(2026, 11, 3, tzinfo=UTC)


def source_ledger():
    ledger = MemoryLedger()
    for source, ref, title in [('listing_counts', 'count:state:placeholder_area', 'placeholder supply'),
                               ('check_counts', 'total:placeholder_area', 'placeholder demand')]:
        ident = 'placeholder_' + source
        ledger.save_series({'id': ident, 'tenant_id': OWNER, 'source': source, 'ref': ref,
                            'unit': 'count', 'engine': 'ffl'})
        ledger.save_points(ident, OWNER, [{'date': '2026-09-01', 'value': 10},
                                         {'date': '2026-10-01', 'value': 12}], stored=True, source=source)
        points = [{**p, 'ref': ref, 'title': title, 'unit': 'count', 'geo': 'placeholder_area',
                   'geo_level': 'state', 'frequency': 'monthly'} for p in ledger.points_for(OWNER, ident)]
        ledger.feed_documents = getattr(ledger, 'feed_documents', []) + [{
            'id': str(uuid4()), 'tenant_id': OWNER, 'fixture': False, 'fetched_at': NOW.isoformat(),
            'source_id': source, 'name': title, 'points': points, 'events': []}]
    return ledger


@pytest.mark.asyncio
async def test_every_fixture_brief_sentence_has_an_exact_source_row_and_url():
    ledger = source_ledger()
    await perform_opportunities(tenant_id=OWNER, engine='ffl', ledger=ledger, now=NOW)
    saved = ledger.reports[-1]
    assert saved['answer'] and len(saved['citations']) == 2
    for sentence in saved['answer'].splitlines():
        citation = next(c for c in saved['citations'] if c['claim'] == sentence)
        assert citation['url'].startswith('https://app.tervory.com/market-lab/sources/')
        ident = citation['url'].split('/sources/')[1].split('?')[0]
        row = int(citation['url'].split('#point-')[1])
        page = await document_page(ledger, OWNER, ident, row=row, engine='ffl')
        assert any(p['index'] == row for p in page['points'])
    text, references = await claims(ledger, OTHER, plan()['bindings'], [{'area': 'placeholder_area'}], now=NOW)
    assert text == '' and references == []
    for batch in list(ledger.pool.batches):
        ledger.remove_batch(OWNER, batch)
    text, references = await claims(ledger, OWNER, plan()['bindings'], [{'area': 'placeholder_area'}], now=NOW)
    assert text == '' and references == []


@pytest.mark.asyncio
async def test_unsourced_recommendations_are_omitted_and_empty_brief_is_held():
    from test_market_lab import AREAS
    ledger = MemoryLedger()
    await perform_opportunities(tenant_id=OWNER, engine='ffl', ledger=ledger, areas=AREAS,
                                signals={'thin': {'no_website': True, 'size': 100}}, now=NOW)
    saved = ledger.reports[-1]
    assert saved['answer'] == '' and saved['citations'] == []
    assert all(d['status'] == 'held' and d['reason'] == 'no_cited_claims' for d in ledger.brief_deliveries.values())
