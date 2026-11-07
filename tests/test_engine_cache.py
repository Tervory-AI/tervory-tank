"""Default semantic equivalence remains tenant and context sealed."""
from contextvars import ContextVar
import os

import product_identity

import pytest

from test_engine_memory import remembered  # noqa: F401
from test_tank_tenant_boundaries import boundary  # noqa: F401
from test_engine_ladder import setup_engine, local_gateway


@pytest.mark.asyncio
@pytest.mark.skipif(not os.environ.get('ENGINE_LOCAL_URL'), reason='real cloud-local llama.cpp server required')
async def test_near_repeat_cache_with_real_memory_and_local_model(remembered, monkeypatch):  # noqa: F811
    b = remembered
    req = await setup_engine(b, monkeypatch)
    actor = product_identity.User(str(req.tenant_id), "placeholder-cache-user", "member")
    monkeypatch.setattr(product_identity, "current", ContextVar("placeholder_cache_user", default=actor))
    calls = local_gateway(b, monkeypatch)
    first = await b.tank.run_route(req)
    assert first.content.strip().lower() == 'billing'
    # Recall now includes the first outcome; establish this context once.
    second = await b.tank.run_route(req)
    count = len(calls)
    near = req.model_copy(update={'messages': [b.tank.Message(role='user', content='Please classify: I was charged twice.')]})
    cached = await b.tank.run_route(near)
    assert cached.rung == 4 and cached.content == second.content
    assert cached.cost_usd == 0 and cached.engine['rung'] == 'cache'
    assert cached.engine['memory_hits'] > 0 and cached.engine['would_have_cost_usd'] > 0
    assert len(calls) == count and cached.ledger_id not in {first.ledger_id, second.ledger_id}
    foreign = await b.tank.run_route(near.model_copy(update={'tenant_id': b.tenants[1]}))
    assert foreign.rung != 4 and foreign.engine['memory_hits'] == 0
    changed = req.model_copy(update={'messages': [b.tank.Message(role='user', content='Classify: I was not charged twice.')]})
    assert (await b.tank.run_route(changed)).rung != 4
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.policy SET cache_scope='none' WHERE task_type='engine.classify'")
    assert (await b.tank.run_route(near)).rung != 4
