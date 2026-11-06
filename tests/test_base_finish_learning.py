from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from test_b3_base_room import ROOT as ROOT
from base_product_fixtures import raw
from sources import continuation, learning
from sources.context_dev import ContextDev
from sources.vendor_ledger import PLATFORM_TENANT


def evidence(**changes):
    args = dict(raw={'name': 'Recorded Business', 'state': 'DC'}, code={},
                vendor={'status': 'candidate', 'fields': {'website': 'https://business.example'}},
                truth={'website': 'https://business.example'}, source='Official dated recorded evidence',
                region='us-east', observed_on='2026-11-05')
    args.update(changes)
    return learning.lesson(**args)


def test_vendor_miss_becomes_officially_checked_gold_with_three_snapshots():
    result = evidence()
    assert result['code'] == {}
    assert result['vendor']['fields']['website'] == result['official']['website']
    candidate, = result['candidates']
    assert candidate['label_family'] == 'context-dev:base.find_site:2026-11'
    assert candidate['needs_network'] is True
    assert candidate['expected']['website']['value'] == 'https://business.example'


@pytest.mark.parametrize('changes,status', [
    ({'truth': {}}, 'unverified'),
    ({'truth': {'website': 'https://another.example'}}, 'disagrees'),
    ({'vendor': {'status': 'transport_error'}}, 'unverified'),
    ({'source': None}, 'unverified'),
])
def test_unverified_or_disagreeing_vendor_answers_never_become_labels(changes, status):
    result = evidence(**changes)
    assert result['status'] == status and result['candidates'] == []


def test_existing_code_success_does_not_create_a_vendor_lesson():
    assert evidence(code={'website': {'value': 'https://business.example'}})['candidates'] == []


def test_named_brief_cap_takes_precedence_over_legacy_setting(monkeypatch):
    monkeypatch.setenv('BASE_CTX_MAX_CREDITS', '10')
    monkeypatch.setenv('CONTEXT_DEV_MAX_CREDITS', '500')
    assert ContextDev(None, None, tenant_id=PLATFORM_TENANT, run_id=str(uuid4())).max_credits == 10


class Pool:
    def __init__(self, conn):
        self.conn = conn

    @asynccontextmanager
    async def acquire(self):
        yield self.conn


@pytest.mark.asyncio
async def test_automatic_vendor_rung_requires_completed_code_and_public_platform_data(monkeypatch):
    import sys
    from agents.base.engines import ffl
    monkeypatch.setitem(sys.modules, 'engines.ffl', ffl)
    monkeypatch.setenv('CONTEXT_DEV_API_KEY', 'placeholder-offline-only')
    conn = SimpleNamespace(fetchval=AsyncMock(return_value=None), fetch=AsyncMock())
    pool = Pool(conn)
    trial = AsyncMock(return_value={'records_sent': 1, 'results': [
        {'status': 'candidate', 'credits': 10, 'lessons': 1}]})
    monkeypatch.setattr(continuation, 'run_trial', trial)
    run = uuid4()
    assert (await continuation.run_gaps(pool, None, PLATFORM_TENANT, run))['status'] == 'code_pending'
    conn.fetch.assert_not_called()
    await continuation.run_gaps(pool, None, uuid4(), run)
    trial.assert_not_called()
    conn.fetchval.return_value = 1
    complete = {'website': {'value': 'https://business.example'}, 'phones': {'value': ['2025550100']},
                'categories': {'value': ['retail']}, 'name': {'value': 'Recorded Business'}}
    gap = {'name': {'value': 'Recorded Business'}}
    conn.fetch.return_value = [
        {'id': uuid4(), 'raw': raw(), 'profile': complete},
        {'id': uuid4(), 'raw': {'name': 'Private source'}, 'profile': gap},
        {'id': uuid4(), 'raw': raw(), 'profile': gap},
    ]
    monkeypatch.setattr(continuation, 'official_truth', lambda: {})
    result = await continuation.run_gaps(pool, None, PLATFORM_TENANT, run)
    assert result['code_records'] == 3
    assert result['credits'] == 10 and result['lessons'] == 1
    selected = trial.await_args.args[-1]
    assert len(selected) == 1 and selected[0]['record_id'] == str(conn.fetch.return_value[-1]['id'])


@pytest.mark.asyncio
async def test_ask_or_denied_admission_never_calls_vendor_or_reserves_credit(monkeypatch):
    monkeypatch.setenv('CONTEXT_DEV_API_KEY', 'placeholder-offline-only')
    http, ledger = AsyncMock(), AsyncMock()
    adapter = ContextDev(http, ledger, tenant_id=PLATFORM_TENANT, run_id=str(uuid4()))
    monkeypatch.setattr(adapter, '_paid_admission', AsyncMock(side_effect=RuntimeError('fixture approval pending')))
    with pytest.raises(RuntimeError):
        await adapter.lookup(name='Recorded Business', record_id=str(uuid4()))
    ledger.reserve.assert_not_called()
    http.post.assert_not_called()


@pytest.mark.asyncio
async def test_lesson_storage_is_tenant_scoped_and_never_writes_serving_profile():
    tenant, run, record = uuid4(), uuid4(), uuid4()
    conn = SimpleNamespace(fetchrow=AsyncMock(return_value={'raw': {'name': 'Recorded Business'}, 'profile': {}}),
                           execute=AsyncMock())
    learned = await learning.save_lesson(conn, tenant, run,
        {'record_id': str(record), 'checked_answers': {'website': 'https://business.example'},
         'label_source': 'Official dated recorded evidence'},
        {'status': 'candidate', 'fields': {'website': 'https://business.example'}, 'observed_on': '2026-11-05'})
    assert len(learned['candidates']) == 1
    sql, *args = conn.execute.await_args.args
    assert 'WHERE tenant_id=$1 AND task_id=$2 AND id=$3' in sql
    assert 'SET profile=' not in sql
    assert args[:3] == [tenant, run, record]


@pytest.mark.asyncio
async def test_gold_reader_never_exports_other_region_or_unchecked_lessons():
    conn = SimpleNamespace(fetch=AsyncMock(return_value=[{'lesson': evidence()},
        {'lesson': evidence(region='za')}]))
    result = await learning.read_lessons(Pool(conn), 200, 'us-east')
    assert len(result) == 1 and result[0]['region'] == 'us-east'
    sql = conn.fetch.await_args.args[0]
    assert "->>'status'='checked'" in sql and 'tenant_id=$1' in sql
