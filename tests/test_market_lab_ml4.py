"""ML4 offline fixtures only: no live data, providers, encoder downloads or UI."""
import hashlib
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents/market_lab'))
from chassis.memory import MemoryClient
from chassis.tank import TankClient
from core import patterns
from core.evidence import gated_facts
from core.jobs import perform_research
from core.ledger import MemoryLedger
from core.predictions import calibration, gate, metadata
from core.pure import make_prediction
from core.warning_stats import analyze
from core.warning_store import series
from engines.ffl.engine import load_map, plan
from engines.ffl.warnings import plan as warning_plan
from feeds.catalog import sources
from feeds.collect import collect
from feeds.keys import key_name_for

TENANT, OTHER = str(uuid4()), str(uuid4())
NOW = datetime(2026, 11, 3, tzinfo=UTC)
FIXTURES = ROOT / 'tests/fixtures/feeds'


@pytest.fixture(autouse=True)
def no_gateway(monkeypatch):
    calls = []
    async def fail(*args, **kwargs):
        calls.append(args)
        raise AssertionError('ML4 must never call the model gateway')
    monkeypatch.setattr(TankClient, 'route', fail)
    yield
    assert calls == []


def test_extracted_plans_are_byte_identical_before_the_explicit_additions():
    assert hashlib.sha256(json.dumps(plan()).encode()).hexdigest() == '836d44f801904dcb2c0f5b82031cbf246fc2713b03c2b2fa3cb928705ba35285'
    original = warning_plan()
    original['pairs'] = original['pairs'][:2]
    original['signals'] = original['signals'][:6]
    assert hashlib.sha256(json.dumps(original).encode()).hexdigest() == '4ec26b246b29e5cd47ffaab92fc727d7a8896b9f56cb97673fa8c1183a562ded'
    assert all(row['store'] is False and row['source'] == 'fred' for row in plan()['costs'])


@pytest.mark.parametrize('change', ['unknown', 'missing', 'nested', 'source', 'downstream', 'threshold', 'fred'])
def test_bad_supply_map_refused(tmp_path, change):
    data = load_map()
    if change == 'unknown': data['surprise'] = True
    if change == 'missing': del data['plan']['supply'][0]['note']
    if change == 'nested': data['warnings']['pairs'][0]['surprise'] = True
    if change == 'source': data['warnings']['pairs'][0]['source'] = 'placeholder_unknown'
    if change == 'downstream': data['warnings']['pairs'][0]['downstream_source'] = 'placeholder_unknown'
    if change == 'threshold': data['warnings']['pairs'][0]['window'] = True
    if change == 'fred': data['plan']['costs'][0]['store'] = True
    path = tmp_path / 'supply_map.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError): load_map(path)


def test_duplicate_json_fields_refused(tmp_path):
    path = tmp_path / 'duplicate.json'
    path.write_text('{"plan":{},"plan":{},"warnings":{}}')
    with pytest.raises(ValueError): load_map(path)


@pytest.mark.asyncio
@pytest.mark.parametrize('config', warning_plan()['pairs'][2:], ids=lambda row: row['id'])
async def test_each_new_pair_uses_keyless_real_format_fixture_series_and_source_document(config):
    spec = next(row for row in sources('ffl') if row.id == config['source'])
    assert key_name_for(spec) == ''
    collected = collect(spec, fixtures=str(FIXTURES), backfill=True, client=SimpleNamespace(documents=[]))
    assert collected['points'] or collected['events']
    if spec.id != 'noaa_alerts':
        assert any(row['ref'] == config['ref'] for row in collected['points'])
    # Explicit offline episode history, using the unchanged statistical detector.
    start = date(2020, 1, 1)
    triggers = [42 + 126 * i for i in range(4)]
    upstream, downstream = [], []
    document = str(uuid4())
    for days in range(0, triggers[-1] + 8, 7):
        point = {'date': (start + timedelta(days=days)).isoformat(),
                 'document_id': document, 'href': '/market-lab/sources/' + document}
        upstream.append({**point, 'value': (70 if config['direction'] == 'drop' else 130) if days in triggers else 100})
        downstream.append({**point, 'value': 1 if any(t + 35 <= days <= t + 56 for t in triggers) else 2})
    stats = analyze(upstream, downstream, config, start + timedelta(days=triggers[-1] + 7))
    assert stats['episode_count'] == stats['hits'] == 3
    assert all(row['upstream']['document_id'] == document for row in stats['episodes'])
    assert stats['current']['point']['href'].endswith(document)
    assert config['outcome_words'] == 'became unavailable'
    assert config['prediction_words'] == 'may become unavailable'


@pytest.mark.asyncio
async def test_weather_is_national_deduplicated_cited_and_uses_stored_events_only(monkeypatch):
    spec = next(row for row in sources('ffl') if row.id == 'noaa_alerts')
    data = collect(spec, fixtures=str(FIXTURES), backfill=True, client=SimpleNamespace(documents=[]))
    event = data['events'][0]
    ident = str(uuid4())
    doc = {**data, 'id': ident, 'points': [], 'events': [event, {**event, 'geo': 'TX'}]}
    future = {**event, 'date': '2099-01-01', 'url': 'https://placeholder.invalid/future'}
    class Connection:
        async def fetch(self, query, *args):
            assert 'tenant_id=$1' in query and str(args[0]) == TENANT
            if args[0] != __import__('uuid').UUID(TENANT): return []
            return [{'content': doc}, {'content': {**doc, 'events': [event, future]}}]
    async def no_request(*args, **kwargs): raise AssertionError('no weather fetch allowed')
    monkeypatch.setattr(httpx.AsyncClient, 'request', no_request)
    result = await series(SimpleNamespace(conn=Connection()), TENANT, NOW)
    weather = result['noaa_alerts:severe_weather:US']
    assert weather['ref'] == 'severe_weather:US'
    assert len(weather['points']) == 1 and weather['points'][0]['value'] == '1'
    point = weather['points'][0]
    assert point['document_id'] == ident and '#event-' in point['href']
    assert point['evidence'][0]['document_id'] == ident


def original(age=90, **extra):
    made = NOW - timedelta(days=age)
    row = make_prediction(tenant_id=TENANT, statement='placeholder saved statement', metric_series_id='placeholder_series',
                          comparator='gte', target=2, made_at=made, resolve_by=made + timedelta(days=28),
                          rationale='placeholder saved rationale')
    return metadata({**row, 'confidence': .5, 'kind': 'placeholder_pair', 'feed': 'placeholder_feed', **extra})


def resolve(row, **extra):
    return {**row, 'id': str(uuid4()), 'outcome': 'hit', 'resolved_at': row['resolve_by'],
            'sources': [{'resolves': row['id']}], **extra}


@pytest.mark.parametrize('age,opened', [(89, False), (90, True)])
def test_ninety_day_gate_uses_resolved_original_and_same_cohort_as_calibration(age, opened):
    row = original(age)
    rows = [row, resolve(row), resolve(row), {**original(200), 'tenant_id': OTHER}]
    cohort = gate(rows, TENANT, now=NOW)['cohorts'][0]
    assert cohort['open'] is opened and cohort['days_covered'] == age and cohort['resolved_count'] == 1
    assert bool(cohort['reason']) is (not opened)
    curve = calibration(rows, TENANT)['curves'][0]
    assert tuple(cohort[key] for key in ('kind', 'feed', 'horizon_seconds')) == tuple(curve[key] for key in ('kind', 'feed', 'horizon_seconds'))
    assert gate(rows, OTHER, now=NOW)['cohorts'][0]['open'] is False


@pytest.mark.parametrize('bad', ['unresolved', 'premature', 'unmeasurable', 'foreign', 'unknown_confidence'])
def test_old_invalid_or_unresolved_rows_cannot_open_gate(bad):
    row = original(200)
    result = resolve(row)
    if bad == 'unresolved': result = None
    if bad == 'premature': result['resolved_at'] = row['made_at']
    if bad == 'unmeasurable': result['outcome'] = 'not_measurable'
    if bad == 'foreign': result['tenant_id'] = OTHER
    if bad == 'unknown_confidence': row['confidence'] = None
    state = gate([row] + ([result] if result else []), TENANT, now=NOW)['cohorts'][0]
    assert not state['open'] and state['resolved_count'] == 0 and state['days_covered'] == 0


@pytest.mark.asyncio
async def test_brief_fact_and_passage_assembly_reject_closed_warning_and_prediction_cohorts():
    ledger = MemoryLedger()
    doc_id = str(uuid4())
    warning_id = str(uuid4())
    row = original(89, sources=[{'warning_id': warning_id, 'evidence': '/market-lab/sources/' + doc_id}])
    ledger.save_prediction(row)
    ledger.save_prediction(resolve(row))
    ledger.feed_documents = [{'id': doc_id, 'tenant_id': TENANT, 'fixture': False, 'kind': 'warning_evidence'}]
    facts = [{'text': 'placeholder claim', 'claim': 'placeholder claim', 'url': '/market-lab/sources/' + doc_id},
             {'text': 'placeholder claim', 'prediction_id': row['id'], 'kind': 'prediction'},
             {'text': 'placeholder claim', 'warning_id': warning_id}]
    assert await gated_facts(ledger, TENANT, facts, now=NOW) == []
    answer = await perform_research(tenant_id=TENANT, ledger=ledger, question='placeholder', passages=facts, now=NOW)
    assert answer['citations'] == [] and answer['answer'] == ''
    row['made_at'] = NOW - timedelta(days=90)
    row['resolve_by'] = row['made_at'] + timedelta(days=28)
    ledger.predictions = [row, resolve(row)]
    assert len(await gated_facts(ledger, TENANT, facts, now=NOW)) == 3
    assert await gated_facts(ledger, OTHER, facts, now=NOW) == []


@pytest.mark.asyncio
async def test_pattern_claim_whitelist_stable_retry_and_sql_listing_only():
    config = warning_plan()['pairs'][0]
    stats = {'lag_min': 7, 'lag_max': 14, 'lag_median': 10, 'episode_count': 3, 'hits': 2, 'hit_rate': 2/3,
             'product_name': 'placeholder_private_product', 'url': 'https://placeholder.invalid',
             'tenant_id': TENANT, 'watch_id': 'placeholder_watch'}
    claim = patterns.claim(config, stats)
    assert set(claim) == patterns.FIELDS
    assert all(value not in json.dumps(claim) for value in (TENANT, 'placeholder_private_product', 'placeholder_watch', 'https://'))
    requests = []
    doc = str(uuid4())
    def handle(request):
        requests.append(request)
        if request.method == 'POST':
            body = json.loads(request.content)
            assert request.url.path == '/memories' and body['kind'] == 'warning_pattern'
            assert body['evidence'] == [doc] and body['source'] == doc
            return httpx.Response(201, json={'id': body['id']})
        assert request.url.path == '/records' and request.url.params['tier'] == 'platform'
        return httpx.Response(200, json={'memories': []})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        memory = MemoryClient(base_url='http://placeholder-hermes', api_key='placeholder-room', http=http)
        assert await patterns.remember(memory, TENANT, config, stats, doc)
        assert await patterns.remember(memory, TENANT, config, stats, doc)
        assert await memory.records(TENANT, tier='platform') == []
    assert json.loads(requests[0].content)['id'] == json.loads(requests[1].content)['id']
    assert all(request.url.path != '/recall' for request in requests)
