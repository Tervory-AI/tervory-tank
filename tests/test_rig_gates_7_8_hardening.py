"""Runtime regressions; central Gate 7/8 acceptance remains on Tank's platform."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from rig_memory_fakes import FakeMemory
from gates_memory import (
    MemoryScopeError,
    is_cache_eligible,
    memory_enabled,
    run_with_memory,
    task_input_fingerprint,
)


@pytest.mark.asyncio
async def test_unset_memory_never_reads_writes_or_reuses(monkeypatch):
    monkeypatch.delenv('RIG_MEMORY_ENABLED', raising=False)
    assert memory_enabled() is False
    import yaml
    root = Path(__file__).resolve().parents[1]
    service = yaml.safe_load((root / 'agents/rig/docker-compose.yml').read_text())['services']['agent-rig']
    assert service['environment']['RIG_MEMORY_ENABLED'] == '${RIG_MEMORY_ENABLED:-false}'
    memory = SimpleNamespace(records=AsyncMock(), recall=AsyncMock(), remember=AsyncMock())
    paid = AsyncMock(return_value={'cost_usd': 0, 'tokens_in': 0, 'tokens_out': 0,
                                 'result': {'content': 'placeholder code answer'}})
    result = await run_with_memory(memory, tenant_id=str(uuid4()), user_id='placeholder-owner',
        task_key='rig.ask', task={'question': 'placeholder'}, paid_call=paid)
    assert result['memory_status'] == 'off' and result['cost_usd'] == 0
    memory.records.assert_not_called()
    memory.recall.assert_not_called()
    memory.remember.assert_not_called()
    paid.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['records', 'recall', 'remember'])
@pytest.mark.parametrize('status', [401, 403])
async def test_memory_auth_failure_is_never_an_outage_or_cached_answer(monkeypatch, operation, status):
    monkeypatch.setenv('RIG_MEMORY_ENABLED', 'true')
    memory = FakeMemory()
    setattr(memory, operation, AsyncMock(side_effect=RuntimeError(f'hermes answered {status}')))
    paid = AsyncMock(return_value={'cost_usd': 0.05, 'tokens_in': 10, 'tokens_out': 3,
                                  'result': {'content': 'placeholder paid answer'}})
    with pytest.raises(MemoryScopeError, match='authorization refused'):
        await run_with_memory(memory, tenant_id=str(uuid4()), user_id='placeholder-owner',
            task_key='rig.ask', task={'question': 'placeholder'}, paid_call=paid)
    assert paid.await_count == (1 if operation == 'remember' else 0)


def test_fingerprint_covers_all_business_input_and_only_ignores_run_identity():
    original = {'question': 'placeholder', 'messages': [{'role': 'system', 'content': 'placeholder-a'}],
                'catalogue_version': 'placeholder-v1', 'task_id': str(uuid4())}
    same = {**original, 'task_id': str(uuid4())}
    assert task_input_fingerprint(original) == task_input_fingerprint(same)
    for changed in ({'question': 'placeholder changed'}, {'catalogue_version': 'placeholder-v2'},
                    {'messages': [{'role': 'system', 'content': 'placeholder-b'}]}):
        assert task_input_fingerprint(original) != task_input_fingerprint({**original, **changed})
    assert is_cache_eligible('rig.ask')
    assert not is_cache_eligible('rig.payment')
    assert not is_cache_eligible('rig.forge.submit')


@pytest.mark.asyncio
async def test_unknown_cost_stays_unknown_and_cannot_seed_zero_cost_reuse(monkeypatch):
    monkeypatch.setenv('RIG_MEMORY_ENABLED', 'true')
    memory = FakeMemory()
    paid = AsyncMock(return_value={'cost_usd': None, 'tokens_in': 10, 'tokens_out': 3,
                                  'result': {'content': 'placeholder answer'}})
    arguments = dict(tenant_id=str(uuid4()), user_id='placeholder-owner', task_key='rig.ask',
                     task={'query': 'placeholder'}, paid_call=paid)
    first = await run_with_memory(memory, **arguments)
    second = await run_with_memory(memory, **arguments)
    assert first['cost_usd'] is None and second['cost_usd'] is None
    assert paid.await_count == 2 and not second['answered_from_memory']


@pytest.mark.asyncio
@pytest.mark.parametrize('cost', [None, 0, 0.0123])
async def test_shipped_model_client_never_fills_in_fixture_prices(monkeypatch, cost):
    monkeypatch.delenv('RIG_BRAIN_ENABLED', raising=False)
    path = Path(__file__).resolve().parents[1] / 'agents/rig/app.py'
    spec = importlib.util.spec_from_file_location('rig_price_regression', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from rigbox import savings
    receipt = {'tokens_in': 0, 'tokens_out': 0}
    token = savings.active.set(receipt)
    ledger = str(uuid4())
    tank = SimpleNamespace(route=AsyncMock(return_value={
        'content': 'placeholder answer', 'cost_usd': cost, 'tokens_in': 10,
        'tokens_out': 3, 'ledger_id': ledger}))
    try:
        answer = await module._TankModels(tank).complete(str(uuid4()), 'rig.ask',
            [{'role': 'user', 'content': 'placeholder'}])
        assert answer == 'placeholder answer'
        assert receipt['cost'] == (None if cost is None else str(cost))
        assert receipt['tokens_in'] == 10 and receipt['tokens_out'] == 3
        assert receipt['model_ledger_ids'] == [ledger]
    finally:
        savings.active.reset(token)


@pytest.mark.asyncio
async def test_model_bracket_rejects_actor_tenant_mismatch_before_any_work(monkeypatch):
    from actor_context import reset_verified_actor, set_verified_actor
    from test_rig import _load_rig_app
    module = _load_rig_app()
    tank = SimpleNamespace(route=AsyncMock())
    models = module._TankModels(tank)
    token = set_verified_actor(tenant_id=str(uuid4()), user_id='placeholder-owner')
    try:
        with pytest.raises(MemoryScopeError):
            await models.complete(str(uuid4()), 'rig.ask', [{'role': 'user', 'content': 'placeholder'}])
    finally:
        reset_verified_actor(token)
    tank.route.assert_not_called()


def test_savings_preserves_all_worker_ledger_ids_and_code_repeat_zero():
    from rigbox.savings import active, memory_result, model_result, model_started
    run = {'tokens_in': 0, 'tokens_out': 0}
    token = active.set(run)
    try:
        model_started()
        memory_result()
        assert run['cost'] == '0' and run['cost_status'] == 'recorded'
        ids = [str(uuid4()), str(uuid4())]
        model_started()
        model_result({'cost_usd': 0.1, 'tokens_in': 20, 'tokens_out': 6, 'ledger_ids': ids})
        assert run['model_ledger_ids'] == ids and run['cost'] == '0.1'
    finally:
        active.reset(token)
