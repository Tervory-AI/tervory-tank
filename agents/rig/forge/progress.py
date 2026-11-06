"""Public build progress: measured time and ledger amounts with their basis."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID


def category(source):
    if source == 'intake': return 'understand'
    if source in {'model_check', 'validate'}: return 'check'
    return 'design'


def cost(receipts):
    rows = {}
    for receipt in receipts:
        try:
            identity = str(UUID(receipt['ledger_id']))
            amount = Decimal(str(receipt['cost_usd']))
            if not amount.is_finite() or amount < 0: continue
            rows[identity] = (amount, receipt.get('cost_basis', 'recorded'))
        except (KeyError, ValueError, TypeError, InvalidOperation):
            continue
    return {'amount_usd': str(sum((r[0] for r in rows.values()), Decimal(0))) if rows else None,
            'basis': 'upper_bound' if any(r[1] == 'upper_bound' for r in rows.values()) else 'recorded' if rows else 'unknown',
            'receipt_ids': list(rows)}


def event(identity, stage, *, at=None, elapsed_ms=0, receipts=(), outcome='delivered'):
    return {'id': str(identity), 'stage': stage, 'at': at or datetime.now(timezone.utc).isoformat(),
            'elapsed_ms': max(0, int(elapsed_ms)), 'outcome': outcome, 'cost': cost(receipts)}
