"""Tenant-owned run receipts. Unknown prices and unknown actual costs stay null."""
import copy
import json
import math
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from core import research_adapter


def money(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid receipt cost')
    return value


async def record(connection, tenant, operation, payload, result, *, run_id=None, cached=False):
    ident = str(UUID(run_id)) if run_id else str(uuid4())
    cached = bool(cached or result.get("answered_from_memory"))
    # Cache hits are new zero-cost runs, never copies of an older paid receipt.
    parts = [] if cached else result.get('receipts', [])
    costs = [money(r.get('cost_usd')) for r in parts]
    cost = (sum(costs) if all(c is not None for c in costs) else None) if parts else money(result.get('cost_usd', 0))
    if cached:
        cost = 0
    # An unavailable/failed answer is not a successful free code operation or
    # a basis for a hypothetical saving. Retain any real paid receipts only.
    comparison = None if result.get('status') in {'unavailable', 'failed', 'error'} else await research_adapter.price_reference(
        tenant, operation, payload, result, run_id=ident)
    receipt = {'id': ident, 'operation': operation, 'made_at': datetime.now(UTC).isoformat(),
        'cost': cost, 'would_have_cost': None, 'baseline_model': None, 'comparison_status': 'unpriced',
        'cache_hit': bool(cached), 'ledger_ids': [r['ledger_id'] for r in parts],
        'tokens_in': 0 if cached else int(result.get('tokens_in',sum(int(r.get('tokens_in') or 0) for r in parts)) or 0),
        'tokens_out': 0 if cached else int(result.get('tokens_out',sum(int(r.get('tokens_out') or 0) for r in parts)) or 0),
        'memory_unavailable': bool(result.get('memory_unavailable'))}
    if cached and result.get('would_have_cost') is not None:
        receipt.update(would_have_cost=money(result['would_have_cost']), comparison_status='measured', comparison_basis='prior_paid_receipt')
    if comparison:
        # Exact personal reuse carries the measured previous paid receipt.
        # A fresh tokenizer-based reference must not replace that evidence.
        if not (cached and result.get('would_have_cost') is not None):
            receipt.update({key: comparison.get(key) for key in ('would_have_cost', 'baseline_model',
                'comparison_status', 'reference_tokens_in', 'reference_tokens_out', 'priced_at')})
        money(receipt['would_have_cost'])
        if comparison.get('ledger_id'):
            receipt['ledger_ids'].append(str(UUID(comparison['ledger_id'])))
    @asynccontextmanager
    async def storage():
        from core.execution import active_ledger
        shared = active_ledger.get()
        if shared is not None:
            yield shared
        else:
            async with connection() as ledger:
                yield ledger
    async with storage() as ledger:
        if hasattr(ledger, 'conn'):
            await ledger.conn.execute('''INSERT INTO agent_market_lab.run_receipts(tenant_id,id,operation,receipt)
                VALUES($1,$2,$3,$4::jsonb) ON CONFLICT(tenant_id,id) DO NOTHING''',
                UUID(tenant), UUID(ident), operation, json.dumps(receipt))
        else:
            ledger.run_receipts = getattr(ledger, 'run_receipts', {})
            ledger.run_receipts.setdefault((tenant, ident), copy.deepcopy(receipt))
    return receipt


async def listing(ledger, tenant):
    if hasattr(ledger, 'conn'):
        rows = await ledger.conn.fetch('SELECT receipt FROM agent_market_lab.run_receipts WHERE tenant_id=$1 ORDER BY made_at DESC,id DESC', UUID(tenant))
        return [json.loads(r['receipt']) if isinstance(r['receipt'], str) else r['receipt'] for r in rows]
    return [copy.deepcopy(r) for (owner, _), r in getattr(ledger, 'run_receipts', {}).items() if owner == tenant]
