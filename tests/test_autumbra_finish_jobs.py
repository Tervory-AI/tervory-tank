import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agents.ghost import app as watch, red_team, threat_queue
from agents.ghost.client_settings import ClientAutumbraSettings, save_settings
from agents.ghost.owner_email_jobs import week_stats_from_receipts
from agents.ghost.store import Store
from agents.ghost.threat_queue import ThreatPayloadQueue, enforce_drain_once
from agents.rig.rigbox.reserve import SmtpMailer
from test_autumbra_cloudflare_hand import payload, TENANT

A = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
B = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_weekly_closed_week_recovers_receipt_failure_and_survives_restart(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'mail'))
    monkeypatch.setenv('THREAT_PAYLOAD_QUEUE_ROOT', str(tmp_path / 'queues'))
    monkeypatch.setenv('AUTUMBRA_SMTP_HOST', 'smtp.example.test')
    monkeypatch.setenv('AUTUMBRA_SMTP_FROM', 'autumbra@example.test')
    letters = []

    async def send(self, letter):
        letters.append(letter)

    monkeypatch.setattr(SmtpMailer, 'send', send)
    database = tmp_path / 'watch.sqlite'
    store = Store(database)
    try:
        for tenant in (A, B):
            save_settings(store, ClientAutumbraSettings(tenant_id=tenant, site_name=tenant[0]+'.example.test', owner_email=tenant[0]+'@example.test'))
        queue_a = ThreatPayloadQueue(tmp_path / 'queues' / A)
        queue_b = ThreatPayloadQueue(tmp_path / 'queues' / B)
        broken = queue_a.root / 'receipts' / 'broken.json'
        broken.write_text('{')
        for identity, stamp in [('last-week', '2026-10-28T12:00:00Z'), ('this-week', '2026-11-02T00:00:00Z')]:
            queue_b.write_receipt({'id': identity, 'tenant_id': B, 'role': 'Enforce', 'outcome': 'applied', 'timestamp': stamp})
        app = SimpleNamespace(state=SimpleNamespace(store=store))
        result = await watch.deliver_weekly_owner_updates(app, now=NOW)
        assert result == {'sent': 1, 'unavailable': 1}
        assert len(letters) == 1 and letters[0]['to'] == 'b@example.test'
        assert '1 threats found' in letters[0]['subject']
        assert store.get_state(A, 'owner_weekly_sent') is None
        broken.unlink()
        result = await watch.deliver_weekly_owner_updates(app, now=NOW)
        assert result == {'sent': 1, 'unavailable': 0}
        assert 'Quiet week.' in letters[1]['text']
        store.close()
        store = Store(database)
        app.state.store = store
        assert await watch.deliver_weekly_owner_updates(app, now=NOW) == {'sent': 0, 'unavailable': 0}
        assert len(letters) == 2
    finally:
        store.close()


@pytest.mark.asyncio
async def test_weekly_loop_checks_due_work_before_sleep(monkeypatch):
    delivery = AsyncMock(return_value={'sent': 0, 'unavailable': 0})
    monkeypatch.setattr(watch, 'deliver_weekly_owner_updates', delivery)
    monkeypatch.setattr(watch.asyncio, 'sleep', AsyncMock(side_effect=asyncio.CancelledError))
    app = SimpleNamespace(state=SimpleNamespace())
    with pytest.raises(asyncio.CancelledError):
        await watch._weekly_owner_email_loop(app)
    delivery.assert_awaited_once_with(app)


@pytest.mark.asyncio
async def test_weekly_job_never_uses_fixture_transport(monkeypatch):
    monkeypatch.setattr(watch, 'transport_status', lambda: 'fixture')
    app = SimpleNamespace(state=SimpleNamespace())
    assert await watch.deliver_weekly_owner_updates(app, now=NOW) == {'sent': 0, 'unavailable': 0}


def test_scheduled_exercises_are_durable_separate_and_not_live_statistics(tmp_path):
    database = tmp_path / 'exercises.sqlite'
    store = Store(database)
    try:
        receipts = red_team.scheduled_exercises(store, A, now=NOW)
        assert len(receipts) == len(red_team.EXERCISES) * len(red_team.OWN_SITES)
        assert all(row['kind'] == 'exercise' and row['result'] != 'failed' for row in receipts)
        assert store.get_state(A, 'exercise_receipts') == receipts
        assert store.get_state(B, 'exercise_receipts') is None
        store.close()
        store = Store(database)
        assert red_team.scheduled_exercises(store, A, now=NOW) == []
        next_day = red_team.scheduled_exercises(store, A, now=NOW+timedelta(days=1))
        assert {r['id'] for r in next_day}.isdisjoint(r['id'] for r in receipts)
        stats = week_stats_from_receipts([{'id': 'exercise', 'tenant_id': A, 'kind': 'exercise',
            'role': 'Enforce', 'applied': True, 'timestamp': NOW.isoformat()}],
            tenant_id=A, week_start=NOW-timedelta(days=1), week_end=NOW+timedelta(days=1))
        assert stats['threats_found'] == stats['checks_run'] == 0
        assert not (tmp_path / 'queues').exists()
    finally:
        store.close()


def test_interrupted_queue_drain_records_uncertainty_without_replaying_action(tmp_path, monkeypatch):
    queue = ThreatPayloadQueue(tmp_path / 'queue')
    identity = queue.put(payload('block_ip'))
    settings = ClientAutumbraSettings(tenant_id=TENANT)
    calls = []

    def crash(*args, **kwargs):
        calls.append(True)
        raise RuntimeError('private failure body')

    monkeypatch.setattr(threat_queue, 'apply_from_payload', crash)
    with pytest.raises(RuntimeError):
        enforce_drain_once(queue, settings=settings, data_dir=tmp_path)
    assert (queue.root / 'processing' / (identity + '.json')).exists()
    restarted = ThreatPayloadQueue(queue.root)
    receipt = enforce_drain_once(restarted, settings=settings, data_dir=tmp_path)
    assert receipt['outcome'] == 'edge_unconfirmed' and not receipt['applied']
    assert receipt['queue_item_id'] == identity
    assert calls == [True]
    assert not list((queue.root / 'processing').iterdir())
    assert enforce_drain_once(restarted, settings=settings, data_dir=tmp_path) is None
    assert 'private failure body' not in json.dumps(restarted.list_receipts())


def test_receipt_write_interruption_preserves_last_complete_receipt(tmp_path, monkeypatch):
    from agents.ghost import durable_shields
    queue = ThreatPayloadQueue(tmp_path)
    queue.write_receipt({'id': 'same', 'outcome': 'before'})
    original = durable_shields.os.replace

    def fail_receipt(source, destination):
        if str(destination).endswith('/receipts/same.json'):
            raise OSError('disk unavailable')
        return original(source, destination)

    monkeypatch.setattr(durable_shields.os, 'replace', fail_receipt)
    with pytest.raises(OSError):
        queue.write_receipt({'id': 'same', 'outcome': 'after'})
    assert queue.list_receipts()[0]['outcome'] == 'before'
    assert not list((tmp_path / 'receipts').glob('*.tmp'))
    with pytest.raises(ValueError):
        queue.write_receipt({'id': '../escape'})


@pytest.mark.asyncio
async def test_act_mail_catches_up_across_week_boundary_and_isolates_broken_tenant(tmp_path, monkeypatch):
    from agents.ghost import owner_email_jobs
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'mail'))
    monkeypatch.setenv('AUTUMBRA_SMTP_HOST', 'smtp.example.test')
    monkeypatch.setenv('AUTUMBRA_SMTP_FROM', 'autumbra@example.test')
    start = datetime(2026, 11, 2, tzinfo=timezone.utc)
    monkeypatch.setattr(owner_email_jobs, 'week_bounds', lambda **kw: (start, NOW))
    monkeypatch.setattr(watch, 'smtp_available_since', lambda: (start-timedelta(days=2)).timestamp())
    receipt = {'id': 'sunday-action', 'tenant_id': B, 'applied': True,
               'timestamp': (start-timedelta(hours=1)).isoformat()}

    def receipts(tenant):
        if tenant == A:
            raise RuntimeError('unavailable')
        return [receipt, {**receipt, 'id': 'wrong-tenant', 'tenant_id': A}]

    monkeypatch.setattr(watch, '_receipts_for_tenant', receipts)
    letters = []

    async def send(self, letter):
        letters.append(letter)

    monkeypatch.setattr(SmtpMailer, 'send', send)
    store = Store(tmp_path / 'watch.sqlite')
    try:
        for tenant in (A, B):
            save_settings(store, ClientAutumbraSettings(tenant_id=tenant, owner_email=tenant[0]+'@example.test'))
        app = SimpleNamespace(state=SimpleNamespace(store=store))
        await watch.deliver_act_owner_updates(app)
        await watch.deliver_act_owner_updates(app)
        assert len(letters) == 1 and letters[0]['to'] == 'b@example.test'
        assert '1 threats found' in letters[0]['subject']
    finally:
        store.close()


def test_waf_rule_is_not_counted_as_a_blocked_address():
    receipt = {'id': 'waf', 'tenant_id': A, 'kind': 'waf_managed', 'applied': True,
               'timestamp': NOW.isoformat(), 'undo': {'rule_id': 'owned-waf'}}
    stats = week_stats_from_receipts([receipt], tenant_id=A, week_start=NOW-timedelta(days=1), week_end=NOW)
    assert stats['threats_found'] == 1 and stats['shield'] is None
