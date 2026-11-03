"""Wave 4 code-only contracts with placeholder data and no external services."""
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agents/market_lab'))
from core.brief_sources import claims
from core.evidence import document_page
from core.jobs import perform_opportunities
from core.ledger import MemoryLedger
from engines.ffl.engine import plan
from test_market_lab_ml3 import database as database

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
        for batch in list(ledger.pool.batches):
            if ledger.pool.batches[batch]['status'] == 'held':
                ledger.release_batch(OWNER, batch)
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


@pytest.mark.asyncio
async def test_wilson_confidence_is_existing_code_and_rejects_invalid_counts(database):
    from base_reliability import wilson_lower
    for hits, total in [(0, 0), (0, 3), (3, 3), (180, 200)]:
        response = await database.client.post('/v1/market-lab/internal/confidence',
            json={'tenant_id': OWNER, 'hits': hits, 'total': total},
            headers={'x-tank-key': 'placeholder-market-lab-key'})
        assert response.status_code == 200
        assert response.json()['confidence'] == wilson_lower(hits, total)
    assert wilson_lower(3, 3) < .5
    bad = await database.client.post('/v1/market-lab/internal/confidence',
        json={'tenant_id': OWNER, 'hits': 4, 'total': 3}, headers={'x-tank-key': 'placeholder-market-lab-key'})
    assert bad.status_code == 422
    denied = await database.client.post('/v1/market-lab/internal/confidence', json={'tenant_id': OWNER, 'hits': 1, 'total': 1})
    assert denied.status_code == 401


@pytest.mark.asyncio
async def test_warning_issues_and_returns_frozen_wilson_confidence(database, monkeypatch):
    import json
    from datetime import date, timedelta
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from core import warnings, warning_store, warning_bridge
    from core.ledger import PostgresLedger
    from engines.ffl.warnings import plan as warning_plan
    from base_reliability import wilson_lower
    config = {**warning_plan()['pairs'][0], 'id': 'placeholder_pair', 'source': 'placeholder_upstream',
              'ref': 'placeholder_ref', 'label': 'placeholder upstream', 'downstream_source': 'placeholder_downstream'}
    start = date(2020, 1, 1)
    triggers = [42 + 126 * i for i in range(4)]
    upstream, downstream = [], []
    for days in range(0, triggers[-1] + 8, 7):
        point = {'date': (start + timedelta(days=days)).isoformat()}
        upstream.append({**point, 'value': 70 if days in triggers else 100})
        downstream.append({**point, 'value': 1 if any(t + 35 <= days <= t + 56 for t in triggers) else 2})
    at = datetime.combine(start + timedelta(days=triggers[-1] + 7), datetime.min.time(), UTC)
    module = SimpleNamespace(warning_plan=lambda: {'pairs': [config], 'outcomes': [
        {'source': 'placeholder_downstream', 'label': 'placeholder target'}]},
        warning_series=lambda *args: [{'source': 'placeholder_downstream', 'ref': 'placeholder_target'}])
    monkeypatch.setattr(warnings, 'load_engine', lambda _: module)
    monkeypatch.setattr(warning_store, 'import_series', AsyncMock())
    monkeypatch.setattr(warning_store, 'series', AsyncMock(return_value={
        'placeholder_up': {'source': config['source'], 'ref': config['ref'], 'points': upstream},
        'placeholder_downstream:placeholder_target': {'source': config['downstream_source'],
            'id': 'placeholder_downstream:placeholder_target', 'name': 'placeholder target', 'points': downstream}}))
    calls = []
    async def corridor(operation, payload):
        calls.append((operation, payload))
        response = await database.client.post('/v1/market-lab/internal/' + operation, json=payload,
                                              headers={'x-tank-key': 'placeholder-market-lab-key'})
        assert response.status_code == 200
        return response.json()
    monkeypatch.setattr(warning_bridge, 'call', corridor)
    async with database.pool.acquire() as conn:
        ledger = PostgresLedger(conn)
        await ledger.apply_schema()
        await warnings.run(ledger, OWNER, 'placeholder_engine', now=at,
                           imported=[{'watch': 'placeholder_watch', 'observations': []}])
        saved = await ledger.predictions_for(OWNER)
        assert len(saved) == 1 and saved[0]['confidence'] == pytest.approx(wilson_lower(3, 3))
        assert calls == [('confidence', {'tenant_id': OWNER, 'hits': 3, 'total': 3})]
        assert saved[0]['sources'][-1] == {'confidence_method': 'wilson_lower_95', 'hits': 3, 'total': 3}
        import market_lab_ml3
        displayed = market_lab_ml3.records('predictions', {'predictions': saved})
        assert json.loads(displayed[0]['summary'])['confidence'] == saved[0]['confidence']


@pytest.mark.asyncio
@pytest.mark.parametrize('enabled', [(), ('NOAA_TOKEN',), ('LEGISCAN_API_KEY',), ('NOAA_TOKEN', 'LEGISCAN_API_KEY')])
async def test_scored_events_require_keys_regions_exact_stage_and_owned_evidence(database, monkeypatch, enabled):
    import json
    from core.event_signals import series
    from core.ledger import PostgresLedger
    from engines.ffl.warnings import plan as warning_plan
    for key in ('NOAA_TOKEN', 'LEGISCAN_API_KEY'):
        monkeypatch.delenv(key, raising=False)
    for key in enabled:
        monkeypatch.setenv(key, 'placeholder-configured-only-in-offline-test')
    owner, foreign = uuid4(), uuid4()
    events = {
        'noaa_alerts': [{'kind': 'severe_weather', 'date': '2026-10-01', 'geo': 'CA',
                         'title': 'placeholder weather', 'body': 'placeholder', 'url': 'https://placeholder.example/weather'},
                        {'kind': 'severe_weather', 'date': '2026-10-01', 'geo': 'TX',
                         'title': 'placeholder outside region', 'url': 'https://placeholder.example/outside'}],
        'legiscan': [{'kind': 'bill_status', 'date': '2026-10-01', 'geo': 'CA',
                      'title': 'AB 1 Engrossed', 'body': 'placeholder bill', 'url': 'https://placeholder.example/bill'},
                     {'kind': 'bill_status', 'date': '2026-10-01', 'geo': 'CA',
                      'title': 'AB 2 Not Engrossed', 'body': 'placeholder non-stage', 'url': 'https://placeholder.example/not-stage'}]}
    async with database.pool.acquire() as conn:
        ledger = PostgresLedger(conn)
        await ledger.apply_schema()
        for source, rows in events.items():
            for tenant in (owner, foreign):
                for _ in range(2):  # Repeated snapshots must not inflate event counts.
                    ident = uuid4()
                    content = {'id': str(ident), 'source_id': source, 'events': rows, 'points': []}
                    await conn.execute('INSERT INTO agent_market_lab.feed_documents(id,tenant_id,source_id,fetched_at,fixture,content) VALUES($1,$2,$3,$4,false,$5::jsonb)',
                                       ident, tenant, source, NOW, json.dumps(content))
        base = {'placeholder_supply': {'source': 'listing_counts', 'ref': 'count:state:CA',
                                      'points': [{'date': '2026-10-01', 'value': 1}]}}
        scored = await series(ledger, str(owner), warning_plan(), base, NOW)
        assert len(scored) == len(enabled)
        for row in scored.values():
            assert row['points'][0]['value'] == '1'
            assert row['points'][0]['event_title'] in ('placeholder weather', 'AB 1 Engrossed')
            doc_id = row['points'][0]['document_id']
            saved_owner = await conn.fetchval('SELECT tenant_id FROM agent_market_lab.feed_documents WHERE id=$1', UUID(doc_id))
            assert saved_owner == owner
        assert await series(ledger, str(owner), warning_plan(), {}, NOW) == {}


def test_event_pairs_have_independent_measured_lag_histories():
    from datetime import date, timedelta
    from core.warning_stats import analyze
    from engines.ffl.warnings import plan as warning_plan
    start = date(2020, 1, 1)
    triggers = [0, 126, 252, 378]
    events = [{'date': (start + timedelta(days=t)).isoformat(), 'value': 1,
               'event_title': 'placeholder recorded event'} for t in triggers]
    measured_lags = []
    for config, lag in zip([p for p in warning_plan()['pairs'] if p.get('trigger') == 'event'], (14, 35)):
        outcomes = [{'date': (start + timedelta(days=d)).isoformat(),
                     'value': 1 if any(t + lag <= d <= t + lag + 21 for t in triggers) else 2}
                    for d in range(0, triggers[-1] + 8, 7)]
        stats = analyze(events, outcomes, config, start + timedelta(days=triggers[-1] + 7))
        assert stats['episode_count'] == stats['hits'] == 3
        assert stats['lag_median'] == lag and stats['current'] is not None
        measured_lags.append(stats['lag_median'])
    assert measured_lags == [14, 35]
