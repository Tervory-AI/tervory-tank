import asyncio
from datetime import date
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest

import gold
import training
import tervor_retrain as scheduler
from training_jobs import run
from test_train1 import database as _database

database = _database
TODAY = date(2026, 11, 7)


def test_weekly_versions_catch_up_without_backlog():
    item = scheduler.Schedule(product='base', version='tervor-lite-1.4', starts_on=TODAY, interval_days=7, minutes=120)
    assert item.due(date(2026,11,6)) is None
    assert item.due(date(2026,11,21)) == ('2026-11-21', 'tervor-lite-1.6')


@pytest.mark.asyncio
async def test_unset_is_inert_and_missing_settings_are_plain(monkeypatch):
    monkeypatch.delenv('TERVOR_RETRAIN_ENABLED', raising=False)
    assert await scheduler.once(None) == {'status':'disabled'}
    monkeypatch.setenv('TERVOR_RETRAIN_ENABLED', 'true')
    monkeypatch.delenv('TERVOR_RETRAIN_PLAN', raising=False)
    result = await scheduler.once(None)
    assert result['status'] == 'not_configured' and 'TERVOR_RETRAIN_PLAN' in result['settings']


@pytest.mark.asyncio
async def test_lifespan_starts_new_work_only_after_explicit_opt_in(monkeypatch):
    started, stopped = set(), set()
    async def loop(name='collect'):
        started.add(name)
        try:
            await asyncio.Event().wait()
        finally:
            stopped.add(name)
    async def retrain(rt):
        assert rt == 'runtime'
        await loop('retrain')
    monkeypatch.setattr(training, 'collector_loop', loop)
    monkeypatch.setattr(training, 'schedule_loop', loop)
    monkeypatch.setattr(training, 'runtime', lambda: 'runtime')
    monkeypatch.setattr(scheduler, 'loop', retrain)
    monkeypatch.delenv('TERVOR_RETRAIN_ENABLED', raising=False)
    async with training.lifespan(None):
        await asyncio.sleep(0)
        assert started == {'collect','export','gold','retest'}
    assert stopped == started
    started.clear()
    monkeypatch.setenv('TERVOR_RETRAIN_ENABLED', 'true')
    async with training.lifespan(None):
        await asyncio.sleep(0)
        assert started == {'collect','export','gold','retest','retrain'}
    assert stopped == started


async def prepare(pool, monkeypatch, path):
    path.write_text(json.dumps({'schedules':[dict(product='base', version='tervor-lite-1.0',
        starts_on=TODAY.isoformat(), interval_days=7, minutes=120)]}))
    for key, value in {'TERVOR_RETRAIN_ENABLED':'true','TERVOR_RETRAIN_PLAN':str(path),
        'HF_TRAIN_BASE_MODEL':'fixture/base','HF_TRAIN_BASE_REVISION':'a'*40,'HF_TRAIN_MAX_USD':'3',
        'HF_ORG':'fixture','HF_TOKEN':'fixture-token'}.items():
        monkeypatch.setenv(key,value)
    async with pool.acquire() as conn:
        for i in range(20):
            await training.save_pair(conn, tenant=run.PLATFORM, agent='base', task='base.extract',
                value={'text':f'train {i}'}, output='checked', approved_by='fixture', source='teacher',
                ref=str(i), teacher_model='fixture/model')
        for i in range(200):
            ident = await gold.add_candidate(conn, tenant=run.PLATFORM, skill='base.extract', agent='base',
                value={'text':f'gold {i}'}, expected='checked', source='public', ref=str(i), holdout=True)
            await conn.execute("UPDATE tank.gold_examples SET status='checked',checked_by='fixture' WHERE id=$1", ident)
    return SimpleNamespace(pool=lambda:pool, box_region=lambda:'us-east')


@pytest.mark.asyncio
async def test_claim_is_durable_and_provider_bill_blocks_repeat_or_overspend(database, monkeypatch, tmp_path):
    pool, _ = database
    rt = await prepare(pool, monkeypatch, tmp_path/'plan.json')
    calls = []
    async def invoke(args):
        calls.append(args)
        if '--dry-run' in args:
            return {'status':'ready','cost_usd':'2.00'}
        assert args[args.index('--total-cap')+1] == '3'
        async with pool.acquire() as conn:
            assert await conn.fetchval("SELECT 1 FROM tank.policy_log WHERE task_type='tervor.retrain' AND action='claimed'")
            await conn.execute('''INSERT INTO tank.training_jobs(id,tenant_id,region,model_repo,estimated_usd)
                VALUES('scheduled-fixture',$1,'us-east','fixture/tervor-lite-1.0-base-20261107',2)''', run.PLATFORM)
        return {'status':'running','name':'scheduled-fixture'}
    monkeypatch.setattr(scheduler, 'invoke', invoke)
    assert (await scheduler.once(rt, today=TODAY))['status'] == 'running'
    assert (await scheduler.once(rt, today=TODAY))['status'] == 'held'
    assert len(calls) == 2
    async with pool.acquire() as conn:
        await run.record_receipt(conn, 'scheduled-fixture', Decimal('1.50'))
        await run.record_receipt(conn, 'scheduled-fixture', Decimal('1.50'))
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger') == 1
    assert await scheduler.once(rt, today=TODAY) == {'status':'caught_up'}
    result = await scheduler.once(rt, today=date(2026,11,14))
    assert result['status'] == 'held' and 'cost' in result['reason']
    assert len(calls) == 3 and '--dry-run' in calls[-1]


@pytest.mark.asyncio
async def test_uncertain_submission_is_not_retried_after_restart(database, monkeypatch, tmp_path):
    pool, _ = database
    rt = await prepare(pool, monkeypatch, tmp_path/'plan.json')
    calls = []
    async def invoke(args):
        calls.append(args)
        if '--dry-run' in args:
            return {'status':'ready','cost_usd':'2'}
        raise TimeoutError('fixture')
    monkeypatch.setattr(scheduler, 'invoke', invoke)
    with pytest.raises(TimeoutError):
        await scheduler.once(rt, today=TODAY)
    assert await scheduler.once(rt, today=TODAY) == {'status':'caught_up'}
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_subprocess_is_bounded_killed_and_reaped(monkeypatch):
    events = []
    class Process:
        returncode = None
        async def communicate(self):
            if not events:
                raise TimeoutError('fixture')
            events.append('reaped')
            self.returncode = -9
            return b'', b''
        def kill(self):
            events.append('killed')
    async def create(*args, **kwargs):
        assert '--json' in args and kwargs['stderr'] == asyncio.subprocess.DEVNULL
        assert kwargs['env']['HF_HUB_OFFLINE'] == '0'
        return Process()
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', create)
    with pytest.raises(RuntimeError, match='reserved job'):
        await scheduler.invoke(['--dry-run'])
    assert events == ['killed','reaped']
