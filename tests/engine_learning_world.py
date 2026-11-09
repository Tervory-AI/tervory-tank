"""Shared fake world for the engine learning proofs: real Tank HTTP and SQL, fake models.

Every model answer comes from httpx.MockTransport; nothing reaches a provider.
Memory is a small in-process stand-in for Hermes that keeps facts per tenant.
"""
import json
import uuid

import httpx

import engine_memory
import engine_quality
from test_engine_ladder import enable_local

TRAINED = 'trained-fixture'
PAID = 'luna'
PRICE = '0.000005'  # luna's roster price for 40 tokens in, 2 out


class Models:
    """Fake gateway. Gold input answers 'billing'; a failing rung answers 'technical'."""

    def __init__(self):
        self.calls: list[str] = []
        self.right = {PAID, TRAINED}

    def answer(self, model: str) -> str:
        return 'billing' if model in self.right else 'technical'

    async def __call__(self, request):
        model = json.loads(request.content)['model']
        self.calls.append(model)
        cost = PRICE if model == PAID else '0.00001' if model not in {'local', 'local-large', TRAINED} else '0'
        return httpx.Response(200, headers={'x-litellm-response-cost': cost, 'x-litellm-model-group': model},
            json={'choices': [{'message': {'content': self.answer(model)}}],
                  'usage': {'prompt_tokens': 40, 'completion_tokens': 2}})


class Hermes:
    """Remembers each delivered answer once per tenant and recalls only that tenant's facts."""

    def __init__(self, pool):
        self.pool = pool
        self.facts: dict[tuple, list[str]] = {}

    async def __call__(self, request):
        body = json.loads(request.content)
        tenant = body['tenant_id']
        key = (tenant, body.get('user_id'))
        if request.url.path.endswith('/remember'):
            async with self.pool.acquire() as conn:
                content = await conn.fetchval('SELECT content FROM tank.transcripts WHERE tenant_id=$1 AND ledger_id=$2',
                                              uuid.UUID(tenant), uuid.UUID(body['ledger_id']))
            claim = f'An earlier answer for this task was {content}.'
            known = self.facts.setdefault(key, [])
            if content and claim not in known:
                known.append(claim)
            return httpx.Response(200, json={'remembered': bool(content)})
        rows = [{'tenant_id': tenant, 'claim': claim, 'kind': 'engine.outcome'} for claim in self.facts.get(key, [])]
        return httpx.Response(200, json={'memories': rows})


async def build(b, monkeypatch, task_type='engine.classify'):
    enable_local(monkeypatch)
    monkeypatch.setattr(b.tank, '_roster_cache', None)
    async with b.pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.policy(task_type,model,system_prompt,max_tokens_out,cache_scope)
            VALUES($1,$2,'Return exactly billing or technical, with no explanation.',32,'tenant')""", task_type, PAID)
        for tenant in b.tenants:
            await conn.execute('''INSERT INTO tank.evals(tenant_id,task_type,input,expected)
                VALUES($1,$2,'{"text":"Classify a duplicate charge"}','"billing"')''', tenant, task_type)
    roster = await b.tank._roster_models()

    async def with_trained():
        return [*roster, {'model_name': TRAINED, 'litellm_params': {'model': 'openai/' + TRAINED},
                          'model_info': {'input_cost_per_token': 0, 'output_cost_per_token': 0}}]
    monkeypatch.setattr(b.tank, '_roster_models', with_trained)
    models = Models()
    original = httpx.AsyncClient
    monkeypatch.setattr(b.tank.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(models), **kw))
    hermes = Hermes(b.pool)
    monkeypatch.setattr(engine_memory, 'HTTP', lambda **kw: original(transport=httpx.MockTransport(hermes), **kw))

    async def judge(rt, request, policy, candidate, messages, primary, actual, caller=None):
        # Fake judge: agreement on the label is the verdict. No judge model is called.
        passed = primary.strip() == actual.strip()
        return {'passed': passed, 'scores': {'correctness': int(passed), 'faithfulness': int(passed), 'task': int(passed)},
                'judge': 'fake', 'revision': engine_quality.revision(request.task_type)}
    monkeypatch.setattr(engine_quality, 'assess', judge)
    b.models, b.hermes, b.task_type = models, hermes, task_type
    b.founder = b.native_headers('founder-fixture', 'org_admin')
    return b


async def route(b, tenant, text='Classify: I was charged twice.', task_type=None, user='founder-fixture'):
    # A signed-in workspace user, verified by Tank's own sign-in guard.
    headers = b.native_headers(user, 'member', tenant)
    body = {'tenant_id': str(tenant), 'task_type': task_type or b.task_type,
            'messages': [{'role': 'user', 'content': text}]}
    response = await b.client.post('/v1/route', json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def record_history(b, tenant, count, task_type=None):
    """Earlier accepted paid traffic: distinct requests through the real route, then past their window."""
    for i in range(count):
        await route(b, tenant, f'Classify charge event {i}: a duplicate charge.', task_type, user='ops-fixture')
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.ledger SET accept_after=now()-interval '1 second' WHERE tenant_id=$1 AND task_type=$2",
                           tenant, task_type or b.task_type)
