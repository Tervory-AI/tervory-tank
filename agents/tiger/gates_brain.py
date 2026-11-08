"""Opt-in Tiger task path: exact memory, free code, brain via Tank, receipt.

Tank owns policy, paid admission, durable paid checkpoints and prices.
"""
import json
import os
from gates_memory import Memory, Unavailable, safe


def enabled():
    return os.environ.get('TIGER_BRAIN_ENABLED', 'false').lower() in ('true', '1', 'yes')


def free(task, payload):
    if task == 'tiger.margin' and all(type(payload.get(k)) in (int, float) for k in ('price', 'cost')) and payload['price'] > 0:
        return {'margin': (payload['price'] - payload['cost']) / payload['price']}
    return None


async def run(client, actor, task, payload, paid):
    safe(payload)
    # The shipped switch covers both memory and brain work. The existing pure
    # code path remains useful without enabling either optional subsystem.
    if not enabled():
        return {'result': free(task, payload), 'answered_from_memory': False,
                'paid_calls': 0, 'cost_usd': 0.0, 'tokens_in': 0, 'tokens_out': 0,
                'receipt': {'memory': 'off', 'cost_usd': 0.0,
                            'tokens_in': 0, 'tokens_out': 0}}
    memory = Memory(client, actor.tenant_id, actor.user_id)
    unavailable = False
    recall = []
    try:
        hit = await memory.exact(task, payload)
        if hit:
            old = hit['meta'].get('receipt', {})
            return {'result': hit['meta']['result'], 'answered_from_memory': True, 'paid_calls': 0,
                    'cost_usd': 0.0, 'tokens_in': 0, 'tokens_out': 0,
                    'receipt': {'memory': 'hit', 'cost_usd': 0.0, 'would_have_cost': old.get('cost_usd'),
                                'source_receipt': old.get('ledger_id')}}
        recall = await memory.recall(task)
    except Unavailable:
        unavailable = True
    answer = free(task, payload)
    receipt = {'cost_usd': 0.0, 'tokens_in': 0, 'tokens_out': 0}
    calls = 0
    if answer is None and enabled():
        answer, receipt = await paid(task, payload, recall)
        calls = 1
    if answer is not None and not unavailable:
        try:
            await memory.remember(task, payload, answer, receipt)
        except Unavailable:
            unavailable = True
    return {'result': answer, 'answered_from_memory': False, 'paid_calls': calls,
            'cost_usd': receipt['cost_usd'], 'tokens_in': receipt['tokens_in'], 'tokens_out': receipt['tokens_out'],
            'receipt': {**receipt, 'memory': 'memory unavailable' if unavailable else 'miss'}}


def tank_client(http):
    from chassis.tank import TankClient
    return TankClient(os.environ.get("TANK_URL", "http://tank:8000"),
                      os.environ.get("TANK_KEY_TIGER") or os.environ.get("TANK_KEY", ""), "tiger", http)


async def tank_paid(http, actor, run_id, task, payload, recall):
    data = await tank_client(http).room_task(actor, run_id, [
        {"role": "system", "content": "Tiger: return JSON. Tenant memory: " + json.dumps(recall)},
        {"role": "user", "content": json.dumps({"task": task, "input": payload})}])
    text = data["choices"][0]["message"]["content"]
    try:
        answer = json.loads(text)
    except ValueError:
        answer = {"text": text}
    return answer, data["receipt"]


async def brain_service(http, actor, task, payload, recall, *, run_id=None):
    from uuid import uuid4
    data = await tank_client(http).delegate_task(actor, run_id or str(uuid4()), task, payload, recall)
    return data["result"], data["receipt"]
