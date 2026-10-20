"""Room intake rejects private/cross-region rows and survives missing endpoints."""
from datetime import date
from types import SimpleNamespace
import secrets

import httpx
import pytest
import training

from test_train1 import database as _database

database = _database


def example(**changes):
    return dict(skill_id='base.find_site', input={'name': 'Public fixture'}, expected={'url': 'example.test'},
                label_source='registry fixture', region='us-east', public=True) | changes


@pytest.mark.parametrize('changes', [{'public': False}, {'client_matter': True}, {'tenant_id': 'client'}, {'public': 'true'}, {'region': 'za'},
                                     {'skill_id': 'zenas.retrieve'}, {'label_source': ''}])
def test_reject_unsafe_candidates(changes):
    assert not training.valid_auto_candidate(example(**changes), 'base', 'us-east')


def test_region_is_exact():
    assert training.valid_auto_candidate(example(), 'base', 'us-east')
    assert training.valid_auto_candidate(example(region='za'), 'base', 'za')
    assert not training.valid_auto_candidate(example(), 'base', 'za')


@pytest.mark.parametrize('family', ['', ' ', 42, [], 'a' * 501])
def test_invalid_label_family(family):
    assert not training.valid_auto_candidate(example(label_family=family), 'base', 'us-east')


@pytest.mark.parametrize('family', [None, 'auto:price-gold-109'])
def test_optional_label_family(family):
    assert training.valid_auto_candidate(example(label_family=family), 'base', 'us-east')
@pytest.mark.asyncio
async def test_missing_endpoint_and_room_auth(monkeypatch):
    key = secrets.token_urlsafe(20)
    monkeypatch.setattr(training, 'ROOMS', ('base',))
    monkeypatch.setenv('TANK_KEY_BASE', key)
    monkeypatch.setattr(training, 'runtime', lambda: SimpleNamespace(box_region=lambda: 'us-east'))
    real_client = httpx.AsyncClient
    def respond(request):
        assert request.headers['X-Tank-Key'] == key
        assert request.url.host == 'agent-base'
        return httpx.Response(404)
    monkeypatch.setattr(training.httpx, 'AsyncClient', lambda **kw: real_client(transport=httpx.MockTransport(respond), **kw))
    await training.collect_room_gold(date(2026, 10, 20))


@pytest.mark.asyncio
async def test_cap_dedup_and_no_automatic_approval(database, monkeypatch):
    pool, _ = database
    monkeypatch.setattr(training, 'ROOMS', ('base',))
    monkeypatch.setenv('TANK_KEY_BASE', secrets.token_urlsafe(20))
    monkeypatch.setenv('GOLD_AUTO_MAX', '2')
    rows = [example(input={'n': n}, label_source=f'citation {n}') for n in range(5)] + [example(region='za')]
    real_client = httpx.AsyncClient
    monkeypatch.setattr(training.httpx, 'AsyncClient', lambda **kw: real_client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=rows)), **kw))
    for _ in range(2):
        await training.collect_room_gold(date(2026, 10, 20))
    async with pool.acquire() as conn:
        saved = await conn.fetch('SELECT * FROM tank.gold_examples')
        assert len(saved) == 2
        assert all(r['auto_label'] and r['public'] and r['status'] == 'candidate' and r['region'] == 'us-east' for r in saved)
        assert await conn.fetchval('SELECT count(*) FROM tank.training_pairs') == 0


def test_existing_room_skill_namespaces():
    assert training.valid_auto_candidate(example(skill_id='market.series_fetch'), 'market_lab', 'us-east')
    assert training.valid_auto_candidate(example(skill_id='scan.secrets'), 'radix', 'us-east')
    assert not training.valid_auto_candidate(example(skill_id='scan.secrets'), 'base', 'us-east')


@pytest.mark.parametrize('skill,room', [('market.series_fetch', 'market_lab'), ('scan.secrets', 'radix'), ('ffl.ingest', 'base')])
def test_package_ownership_not_prefix(skill, room):
    assert training.valid_auto_candidate(example(skill_id=skill), room, 'us-east')
    assert not training.valid_auto_candidate(example(skill_id=skill), 'tiger', 'us-east')
    assert not training.valid_auto_candidate(example(skill_id=skill + '.unknown'), room, 'us-east')


@pytest.mark.parametrize('raw', ['', '0', '-1', 'nan', '1.5', 'Infinity', 'no', '9' * 5000])
def test_bad_cap_falls_back_once(monkeypatch, caplog, raw):
    monkeypatch.setenv('GOLD_AUTO_MAX', raw)
    assert training.gold_auto_max() == 200
    assert sum('Invalid GOLD_AUTO_MAX' in record.message for record in caplog.records) == 1


def test_positive_and_absent_cap(monkeypatch, caplog):
    monkeypatch.delenv('GOLD_AUTO_MAX', raising=False)
    assert training.gold_auto_max() == 200
    monkeypatch.setenv('GOLD_AUTO_MAX', '12')
    assert training.gold_auto_max() == 12
    assert not caplog.records


@pytest.mark.asyncio
async def test_bad_rows_savepoint_and_later_rooms(database, monkeypatch):
    import json
    pool, _ = database
    monkeypatch.setattr(training, 'ROOMS', ('base', 'market_lab', 'radix'))
    for room in training.ROOMS:
        monkeypatch.setenv('TANK_KEY_' + room.upper(), secrets.token_urlsafe(20))
    bad = [example(input={'value': value}) for value in ('\x00', float('nan'), float('inf'), -float('inf'))]
    bad += [example(input=[]), example(expected='wrong'), example(label_source='\x00')]
    bad += [example(**{field: {'large': 'é' * 40000}}) for field in ('input', 'expected')]
    bad += [example(input={'large': 'x' * 33000}, expected={'large': 'x' * 33000})]
    rows = [example(input={'n': 1})] + bad + [example(input={'n': 2}, skill_id='ffl.ingest')]
    real_client = httpx.AsyncClient
    def respond(req):
        payload = rows if req.url.host == 'agent-base' else [example(skill_id='market.series_fetch' if req.url.host == 'agent-market-lab' else 'scan.secrets')]
        # Deliberately malformed JSON numbers are accepted by Python's decoder;
        # row serialization must reject them without rejecting healthy siblings.
        return httpx.Response(200, content=json.dumps(payload).encode())
    monkeypatch.setattr(training.httpx, 'AsyncClient', lambda **kw: real_client(transport=httpx.MockTransport(respond), **kw))
    stats = await training.collect_room_gold(date(2026, 10, 20))
    assert stats['rejected'] == len(bad)
    assert stats['inserted'] == 4 and stats['unavailable'] == 0
    async with pool.acquire() as conn:
        saved = await conn.fetch('SELECT skill_id FROM tank.gold_examples')
        assert {r['skill_id'] for r in saved} == {'base.find_site', 'ffl.ingest', 'market.series_fetch', 'scan.secrets'}


@pytest.mark.asyncio
async def test_stream_body_cap_continues_to_next_room(monkeypatch):
    monkeypatch.setattr(training, 'ROOMS', ('base', 'radix'))
    for room in training.ROOMS:
        monkeypatch.setenv('TANK_KEY_' + room.upper(), secrets.token_urlsafe(20))
    monkeypatch.setattr(training, 'runtime', lambda: SimpleNamespace(box_region=lambda: 'us-east'))
    seen = []
    chunks = []
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for n in range(100):
                chunks.append(n)
                yield b' ' * 65536
    def respond(req):
        seen.append(req.url.host)
        return httpx.Response(200, stream=Stream()) if req.url.host == 'agent-base' else httpx.Response(404)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(training.httpx, 'AsyncClient', lambda **kw: real_client(transport=httpx.MockTransport(respond), **kw))
    stats = await training.collect_room_gold(date(2026, 10, 20))
    assert stats['rejected_responses'] == 1
    assert seen == ['agent-base', 'agent-radix'] and len(chunks) == 81


def test_row_size_byte_boundary():
    import json
    overhead = len(json.dumps({'v': ''}, ensure_ascii=False, sort_keys=True).encode())
    training.candidate_json({'v': 'x' * (65536 - overhead)})
    with pytest.raises(ValueError):
        training.candidate_json({'v': 'x' * (65537 - overhead)})


@pytest.mark.asyncio
@pytest.mark.parametrize("room", ["base", "zenas"])
async def test_explicit_holdout_survives_intake_review_and_correction(database, monkeypatch, room):
    import gold
    pool, _ = database
    monkeypatch.setattr(training, 'ROOMS', (room,))
    monkeypatch.setenv('TANK_KEY_' + room.upper(), secrets.token_urlsafe(20))
    def no_rehash(*args):
        pytest.fail('An explicit holdout must never be re-split')
    monkeypatch.setattr(training, 'is_holdout', no_rehash)
    monkeypatch.setattr(gold, 'is_holdout', no_rehash)
    rows = [example(input={'held': n}, holdout=True) for n in range(2)]
    if room == "zenas":
        from agents.zenas.gold_sources import case_candidate
        from test_zenas_gold_sources import case
        rows = [
            case_candidate(dict(case(holdout=True), pool_version_id=f"held-{number}"), "us-east")
            for number in range(2)
        ]
        assert all(row["public"] is True and row["holdout"] is True for row in rows)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(training.httpx, 'AsyncClient', lambda **kw: real_client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=rows)), **kw))
    for _ in range(2):
        stats = await training.collect_room_gold(date(2026, 10, 20))
        assert stats['rejected'] == 0
    async with pool.acquire() as conn:
        saved = await conn.fetch('SELECT * FROM tank.gold_examples ORDER BY id')
        assert len(saved) == 2 and all(row['holdout'] for row in saved)
    reviewer = gold.Reviewer('founder', gold.PLATFORM_TENANT, True)
    await gold.check(saved[0]['id'], gold.Verdict(action='right'), reviewer)
    await gold.check(saved[1]['id'], gold.Verdict(action='wrong', correction={'fixed': True}), reviewer)
    async with pool.acquire() as conn:
        correction = await conn.fetchrow("SELECT * FROM tank.gold_examples WHERE source='correction'")
        assert correction['holdout'] is True
    await gold.check(correction['id'], gold.Verdict(action='right'), reviewer)
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.training_pairs') == 0
