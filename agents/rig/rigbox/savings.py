"""Tenant receipts for code work, with an idempotent Tank accounting outbox."""
import asyncio
import copy
from contextvars import ContextVar
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from functools import wraps
import json
from uuid import UUID, uuid4
from chassis.tenant_db import tenant_scope

from .token_reference import input_tokens, tokens

active = ContextVar('rig_savings_run', default=None)
active_task = ContextVar('rig_savings_task', default=None)
latest = ContextVar('rig_savings_receipt', default=None)
ACTIONS = ('search', 'product', 'setups', 'graph', 'ask', 'swap', 'compare', 'link_quote',
           'quote', 'locate', 'locate_confirm', 'locate_accept', 'suggest', 'approve', 'reject',
           'apply_watch', 'pull_feeds', 'deliver', 'retry_pending', 'confirm_store_payment')
PRIVATE = {'contact', 'email', 'phone', 'address', 'delivery', 'password', 'secret', 'token',
           'authorization', 'key', 'publishable_key', 'admin_key', 'api_key'}


def sanitized(value):
    if isinstance(value, dict):
        return {str(key): sanitized(item) for key, item in value.items()
                if not any(part in str(key).lower().split('_') for part in PRIVATE)}
    if isinstance(value, (tuple, list)):
        return [sanitized(item) for item in value]
    if isinstance(value, bytes) or callable(value):
        return '[binary or service input]'
    return value


class Receipts:
    def __init__(self, store):
        self.store = store

    async def put(self, tenant, receipt):
        if str(receipt['tenant_id']) != str(tenant):
            raise ValueError('Receipt tenant mismatch')
        pool = getattr(self.store, 'pool', None)
        if pool is None:
            if not hasattr(self.store, '_savings_runs'):
                self.store._savings_runs = {}
            self.store._savings_runs[str(tenant), receipt['id']] = copy.deepcopy(receipt)
        else:
            with tenant_scope(tenant):
                await pool.execute('''INSERT INTO agent_rig.savings_runs(tenant_id,id,receipt)
                    VALUES($1,$2,$3::jsonb) ON CONFLICT(tenant_id,id) DO UPDATE SET receipt=excluded.receipt''',
                    UUID(str(tenant)), UUID(receipt['id']), json.dumps(receipt, default=str))

    async def rows(self, tenant, *, identity=None, pending=False):
        pool = getattr(self.store, 'pool', None)
        if pool is None:
            rows = [copy.deepcopy(value) for (owner, identifier), value in
                    getattr(self.store, '_savings_runs', {}).items()
                    if owner == str(tenant) and (identity is None or identifier == str(identity))]
            rows.sort(key=lambda row: (row['created_at'], row['id']), reverse=True)
            return [row for row in rows if not pending or row.get('accounting') == 'pending'][:100]
        with tenant_scope(tenant):
            values = await pool.fetch('''SELECT receipt FROM agent_rig.savings_runs WHERE tenant_id=$1
                AND ($2::uuid IS NULL OR id=$2) AND (NOT $3::boolean OR receipt->>'accounting'='pending')
                ORDER BY created_at DESC,id DESC LIMIT 100''', UUID(str(tenant)), UUID(str(identity)) if identity else None, pending)
        return [json.loads(row['receipt']) if isinstance(row['receipt'], str) else dict(row['receipt']) for row in values]


def reference(prompt):
    run = active.get()
    if run is not None:
        try:
            run['reference_tokens_in'] += input_tokens([{'role': 'user', 'content': prompt}])
            run['reference_counted'] = True
        except (ValueError, ImportError, OSError):
            run['reference_status'] = 'unavailable'


def model_started():
    run = active.get()
    if run is not None:
        run.setdefault('_model_cost', Decimal(0))
        run['cost'], run['cost_status'] = None, 'unknown'


def model_result(result):
    run = active.get()
    if run is None:
        return
    try:
        ids = result.get('ledger_ids') or [result['ledger_id']]
        run.setdefault('model_ledger_ids', []).extend(str(UUID(str(value))) for value in ids)
        run['tokens_in'] += int(result.get('tokens_in') or 0)
        run['tokens_out'] += int(result.get('tokens_out') or 0)
        value = Decimal(str(result.get('cost_usd', result.get('cost'))))
        if not value.is_finite() or value < 0:
            raise ValueError('Unknown cost')
        run['_model_cost'] = run.get('_model_cost', Decimal(0)) + value
        if not run.get('_model_unknown'):
            run['cost'], run['cost_status'] = str(run['_model_cost']), 'recorded'
    except (ValueError, TypeError, KeyError, InvalidOperation):
        run['_model_unknown'] = True
        run['cost'], run['cost_status'] = None, 'unknown'


def memory_result():
    """A verified stored answer has no new model spend; the outbox books code."""
    run = active.get()
    if run is not None and not run.get('_model_unknown'):
        run['cost'] = str(run.get('_model_cost', Decimal(0)))
        run['cost_status'] = 'recorded'


async def publish(service, receipt):
    tank = getattr(getattr(service, 'models', None), 'tank', None)
    if tank is None or not hasattr(tank, '_post') or receipt.get('outcome') == 'running':
        return
    body = {name: receipt[name] for name in ('id', 'tenant_id', 'action', 'outcome',
            'reference_tokens_in', 'reference_tokens_out', 'reference_status', 'cost', 'cost_status')}
    if receipt.get('model_ledger_ids'):
        body['model_ledger_ids'] = receipt['model_ledger_ids']
    try:
        async with asyncio.timeout(5):
            answer = await tank._post('/v1/agents/rig/savings/receipts', body)
        if (answer.get('id') != receipt['id'] or answer.get('tenant_id') != receipt['tenant_id']
                or Decimal(str(answer.get('cost'))) != Decimal(str(receipt['cost']))):
            raise ValueError('Receipt scope or cost mismatch')
        receipt = {**receipt, **{name: answer[name] for name in
            ('would_have_cost', 'baseline_model', 'baseline_status', 'ledger_id')},
            'accounting': 'pending' if answer['baseline_status'] == 'unpriced' else 'recorded'}
        await Receipts(service.store).put(receipt['tenant_id'], receipt)
    except Exception:
        # Pending is visible in the receipt. Only the receipt delivery is retried;
        # the product operation and any paid work are never rerun by this outbox.
        return


async def reconcile(service, tenant):
    for receipt in await Receipts(service.store).rows(tenant, pending=True):
        await publish(service, receipt)


async def worker(service):
    from chassis.tenant_db import tenant_scope
    while True:
        try:
            with tenant_scope(None, administrative=True):
                tenants = await service.store.tenant_ids()
            for tenant in tenants:
                with tenant_scope(tenant):
                    await reconcile(service, tenant)
        except Exception:
            # Durable pending receipts remain visible and survive worker restart.
            pass
        await asyncio.sleep(30)


def public(receipt):
    return {name: receipt.get(name) for name in ('id', 'action', 'created_at', 'outcome',
            'cost', 'cost_status', 'would_have_cost', 'baseline_model', 'baseline_status',
            'reference_tokens_in', 'reference_tokens_out', 'reference_status', 'tokens_in',
            'tokens_out', 'ledger_id', 'accounting')}


async def view(service, tenant, identity=None):
    rows = [public(row) for row in await Receipts(service.store).rows(tenant, identity=identity)]
    tank = getattr(getattr(service, 'models', None), 'tank', None)
    if tank is not None and hasattr(tank, '_post'):
        try:
            async with asyncio.timeout(3):
                answer = await tank._post('/v1/agents/rig/savings/query',
                    {'tenant_id': str(tenant), 'id': str(identity) if identity else None})
            if answer.get('tenant_id') != str(tenant):
                raise ValueError('Receipt scope mismatch')
            known = {str(row.get('ledger_id') or row['id']) for row in rows}
            rows += [public(row) for row in answer['receipts'] if row['id'] not in known]
        except Exception:
            # Local durable receipts remain available during a Tank outage.
            return {'receipts': rows, 'accounting': 'pending'}
    rows.sort(key=lambda row: (row['created_at'], row['id']), reverse=True)
    return {'receipts': rows[:100]}


def schedule(service, receipt):
    if getattr(getattr(service, 'models', None), 'tank', None) is None:
        return
    tasks = getattr(service, '_savings_tasks', None)
    if tasks is None:
        tasks = service._savings_tasks = set()
    task = asyncio.create_task(publish(service, copy.deepcopy(receipt)))
    tasks.add(task)
    task.add_done_callback(tasks.discard)


def measured(service, action, call):
    @wraps(call)
    async def run(tenant, *args, **kwargs):
        parent = active.get()
        if (parent is not None and parent['tenant_id'] == str(tenant)
                and parent['outcome'] == 'running' and active_task.get() is asyncio.current_task()):
            return await call(tenant, *args, **kwargs)
        receipt = {'id': str(uuid4()), 'tenant_id': str(tenant), 'action': action,
            'outcome': 'running', 'created_at': datetime.now(timezone.utc).isoformat(),
            'cost': '0', 'cost_status': 'recorded', 'would_have_cost': None,
            'baseline_model': None, 'baseline_status': 'pending', 'accounting': 'pending',
            'reference_tokens_in': 0, 'reference_tokens_out': 0, 'reference_status': 'bpe_reference',
            'reference_counted': False, 'tokens_in': 0, 'tokens_out': 0}
        store = Receipts(service.store)
        await store.put(tenant, receipt)
        token = active.set(receipt)
        owner = active_task.set(asyncio.current_task())
        result = None
        try:
            result = await call(tenant, *args, **kwargs)
            receipt['outcome'] = ('failed' if isinstance(result, dict) and
                (result.get('ok') is False or result.get('status') == 'failed' or result.get('error')) else 'delivered')
            return result
        except BaseException:
            receipt['outcome'] = 'failed'
            raise
        finally:
            try:
                if not receipt['reference_counted']:
                    reference(json.dumps({'action': action, 'arguments': sanitized(args),
                                          'options': sanitized(kwargs)}, default=str))
                receipt['reference_tokens_out'] = tokens(sanitized(result))
            except (ValueError, ImportError, OSError):
                receipt['reference_status'] = 'unavailable'
            active.reset(token)
            active_task.reset(owner)
            receipt.pop('_model_cost', None)
            receipt.pop('_model_unknown', None)
            await store.put(tenant, receipt)
            latest.set(copy.deepcopy(receipt))
            schedule(service, receipt)
    return run


def instrument(service):
    from rig_memory import memory_enabled
    if not memory_enabled():
        return
    for name in ACTIONS:
        call = getattr(service, name, None)
        if call is not None:
            setattr(service, name, measured(service, 'rig.' + name, call))
