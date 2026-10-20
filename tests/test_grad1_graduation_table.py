import pytest
import graduate
from test_train1 import database as _database

database = _database


def candidate(name, kind, score=.99, cost=0):
    return dict(candidate=name, kind=kind, heldout_score=score, heldout_n=20, cost_per_call=cost, cheaper=True)


def test_order_and_heldout_gate():
    policy = {'eval_threshold': .97}
    rows = [candidate('owned', 'owned'), candidate('cheap', 'model'), candidate('skill:base.fixture@1', 'code')]
    assert graduate.training_candidate(policy, rows, 99) is None
    assert graduate.training_candidate(policy, rows, 100)['kind'] == 'code'
    rows[-1]['heldout_score'] = .96
    assert graduate.training_candidate(policy, rows, 100)['kind'] == 'model'
    rows[1]['cheaper'] = False
    assert graduate.training_candidate(policy, rows, 100)['kind'] == 'owned'
    rows[0]['heldout_n'] = 0
    assert graduate.training_candidate(policy, rows, 100) is None

@pytest.mark.asyncio
async def test_empty_evidence_does_not_fabricate_costs_or_scores(database):
    pool, _ = database
    from gold import PLATFORM_TENANT
    async with pool.acquire() as conn:
        rows = await graduate.training_table(conn, PLATFORM_TENANT, 'us-east')
    assert rows
    assert all(r['gold_count'] == 0 and r['heldout_score'] is None and r['candidate'] is None
               and r['current_cost'] is None and not r['can_promote'] for r in rows)
