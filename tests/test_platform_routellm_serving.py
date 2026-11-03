"""Offline conditional-serving gate, failure containment and exact router hooks."""
import ast
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import threading
from types import SimpleNamespace
import uuid

import pytest

import graduate
import routellm_shadow as routing

ROOT = Path(__file__).resolve().parents[1]
TENANT = uuid.UUID(int=1)


def policy():
    row = {'model': 'placeholder-strong', 'routellm_weak_model': 'placeholder-weak',
           'routellm_threshold': .5, 'rung': 1, 'max_tokens_out': 64, 'priority': 'standard'}
    row['candidate_model'] = routing.configuration(row).candidate
    return row


def promoted():
    move = graduate.promote_if_proven(policy(), graduate.Evidence(samples=200, agreement=1),
                                      datetime.now(timezone.utc), automatic=False)
    assert move.action == 'promote'
    return move.policy


def tank_stub():
    return SimpleNamespace(model_call_refusal=lambda *args, **kwargs: None, box_region=lambda: 'us-east')


@pytest.mark.parametrize('samples,agreement,automatic,action', [
    (199, 1, False, 'hold'), (200, .989, False, 'hold'),
    (200, .99, True, 'hold'), (200, .99, False, 'promote')])
def test_existing_proof_and_founder_gates(samples, agreement, automatic, action):
    row = policy()
    move = graduate.promote_if_proven(row, graduate.Evidence(samples=samples, agreement=agreement),
                                      datetime.now(timezone.utc), automatic=automatic)
    assert move.action == action
    assert graduate.router_cannot_serve(row['candidate_model'])  # Unchanged generic guard.
    if action == 'promote':
        assert move.policy['previous_model'] == row['model']
        assert move.policy['rung'] == 1 and not move.policy['semantic_cache']
    if automatic:
        assert move.reason == 'proven, waiting for a person'


@pytest.mark.parametrize('field,value', [('model', 'placeholder-other-strong'),
    ('routellm_weak_model', 'placeholder-other-weak'), ('routellm_threshold', .6)])
def test_changed_configuration_cannot_promote(field, value):
    row = policy()
    row[field] = value
    assert graduate.promote_if_proven(row, graduate.Evidence(samples=200, agreement=1),
                                     datetime.now(timezone.utc), automatic=False).action == 'hold'


@pytest.mark.asyncio
@pytest.mark.parametrize('score,expected', [(.2, 'placeholder-weak'), (.5, 'placeholder-strong'), (.8, 'placeholder-strong')])
async def test_serving_scores_last_user_prompt(monkeypatch, score, expected):
    seen = []
    monkeypatch.setattr(routing, 'score', lambda prompt: seen.append(prompt) or score)
    result = await routing.serve(tank_stub(), promoted(), [
        {'role': 'user', 'content': 'placeholder-first'}, {'role': 'assistant', 'content': 'placeholder-answer'},
        {'role': 'user', 'content': 'placeholder-last'}], tenant_id=TENANT)
    assert seen == ['placeholder-last']
    assert result['model'] == expected and result['score'] == score


@pytest.mark.asyncio
@pytest.mark.parametrize('reason', ['busy', 'urgent', 'fingerprint', 'not_promoted', 'refused'])
async def test_strong_fallback_without_scoring(monkeypatch, reason):
    row = promoted()
    tank = tank_stub()
    priority = 'standard'
    if reason == 'busy':
        monkeypatch.setattr(routing, '_pending', 4)
    elif reason == 'urgent':
        priority = 'urgent'
    elif reason == 'fingerprint':
        row['routellm_threshold'] = .6
    elif reason == 'not_promoted':
        row['promoted_at'] = None
    else:
        tank.model_call_refusal = lambda *args, **kwargs: 'placeholder-refused'
    def unexpected(_prompt):
        pytest.fail('scorer must not run for this fallback')
    monkeypatch.setattr(routing, 'score', unexpected)
    decision = await routing.serve(tank, row, [], tenant_id=TENANT, priority=priority)
    assert decision['model'] == 'placeholder-strong' and decision['score'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('invalid', [None, float('nan'), 2])
async def test_failed_or_invalid_scorer_uses_strong(monkeypatch, invalid):
    def score(_prompt):
        if invalid is None:
            raise RuntimeError('placeholder-score-error')
        return invalid
    monkeypatch.setattr(routing, 'score', score)
    result = await routing.serve(tank_stub(), promoted(), [], tenant_id=TENANT)
    assert result['model'] == 'placeholder-strong' and result['score'] is None


@pytest.mark.asyncio
async def test_timeout_retains_slot_until_thread_completes(monkeypatch):
    release = threading.Event()
    def score(_prompt):
        release.wait(timeout=5)
        return .2
    monkeypatch.setattr(routing, 'score', score)
    monkeypatch.setattr(routing, 'SERVE_TIMEOUT_SECONDS', .01)
    try:
        result = await routing.serve(tank_stub(), promoted(), [], tenant_id=TENANT)
        assert result['model'] == 'placeholder-strong'
        assert routing._pending == 1
    finally:
        release.set()
        async def drained():
            while routing._pending:
                await asyncio.sleep(0)
        await asyncio.wait_for(drained(), 2)


def test_deferred_policy_suppresses_both_shadow_paths_and_preserves_decision():
    row = promoted()
    row['candidate_model'] = 'placeholder-stale-candidate'
    decision = {'model': 'placeholder-weak', 'score': .2, 'threshold': .5,
                'weak_model': 'placeholder-weak', 'config': 'placeholder-config'}
    resolved = routing.serving_policy(row, decision)
    assert resolved['rung'] == 1 and resolved['model'] == decision['model']
    assert resolved['candidate_model'] is None and resolved['shadow_rate'] == 0
    assert routing.configuration(resolved) is None
    assert resolved['_routellm_served'] == decision


def test_rollback_restores_strong_model():
    result = graduate.rollback_if_dropped(promoted(), graduate.Evidence(rejected=1, judged=1),
                                          datetime.now(timezone.utc))
    assert result.action == 'rollback' and result.policy['model'] == 'placeholder-strong'
    assert result.policy['previous_model'] is None and result.policy['rung'] == 1


def test_run_route_changes_only_in_the_two_reviewed_hooks():
    source = (ROOT / 'tank/main.py').read_text()
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'run_route')
    function = ast.get_source_segment(source, node)
    old, skipping, hooks = [], False, 0
    for line in function.splitlines(keepends=True):
        if '# BEGIN ROUTELLM SERVING ' in line:
            assert not skipping
            skipping = True
            hooks += 1
        elif '# END ROUTELLM SERVING ' in line:
            assert skipping
            skipping = False
        elif not skipping:
            old.append(line)
    assert hooks == 2 and not skipping
    assert hashlib.sha256(''.join(old).encode()).hexdigest() == '3f33cc4218d786327c064f68aaf2a93cd45675c8ad9d751c9ed0753394a6ebe9'


@pytest.mark.asyncio
async def test_revalidation_resolves_target_and_records_concrete_model(monkeypatch):
    import skala_revalidation as revalidation
    row = promoted()
    statements, calls = [], []
    class Connection:
        async def execute(self, sql, *args):
            statements.append((sql, args))
    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield Connection()
    async def llm(model, messages, max_tokens, *, receipt):
        calls.append((model, messages, max_tokens))
        receipt.update(model=model, tokens_in=1, tokens_out=1, cost=.001)
        return 'placeholder-result', .001
    tank = tank_stub()
    tank.graduate = graduate
    tank.pool = lambda: Pool()
    tank._llm = llm
    monkeypatch.setattr(routing, 'score', lambda _prompt: .2)
    context = SimpleNamespace(calls=0, cost_usd=0)
    job = {'policy': row, 'model': row['model'], 'task_type': 'placeholder.task', 'policy_tenant_id': TENANT}
    token = revalidation.ACTIVE.set(job)
    try:
        result = revalidation.eval_context(tank, SimpleNamespace(agent='placeholder', ref='placeholder.skill@1.0.0'), context)
        output = await result._model(task_type='placeholder.task', messages=[{'role': 'user', 'content': 'placeholder'}])
    finally:
        revalidation.ACTIVE.reset(token)
    assert output['content'] == 'placeholder-result' and calls[0][0] == 'placeholder-weak'
    sql, args = statements[-1]
    assert 'routellm_status' in sql and args[6] == 'placeholder-weak'
    assert args[-1] == 'served' and args[-5] == .2
