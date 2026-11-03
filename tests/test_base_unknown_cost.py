"""Unknown receipt amounts never become a numeric per-record total (offline)."""
from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest

from base_metrics import cost_rows
from base_queries import numbers


@pytest.mark.asyncio
@pytest.mark.parametrize("known,unpriced,missing,verified", [
    ("0", 1, 0, 3), ("6", 1, 0, 3), ("6", 0, 1, 3),
    ("6", 0, 0, 3), ("0", 0, 0, 3), ("6", 0, 0, 0),
])
async def test_database_summary_keeps_incomplete_cost_unknown(known, unpriced, missing, verified):
    # Supply aggregation results to the actual calculator; no database or HTTP.
    class Pool:
        def __init__(self):
            self.results = iter([[], [], [], [{
                "state": "DC", "month": "2026-10", "rung": 1,
                "known": Decimal(known), "unpriced": unpriced, "vendors": ["brave.search"],
                "verified_records": verified, "missing_receipts": missing,
            }]])

        @asynccontextmanager
        async def acquire(self):
            yield self

        async def fetch(self, *_):
            return next(self.results)

        async def fetchval(self, *_):
            return 0

    pool = Pool()
    result = await numbers(SimpleNamespace(rt=SimpleNamespace(pool=lambda: pool)), uuid.UUID(int=2), ["DC"], [], False)
    amount = result["costs"][0]
    assert Decimal(amount["known_cost_usd"]) == Decimal(known)
    if unpriced or missing or not verified:
        assert amount["cost_per_verified_record"] is None
    else:
        assert Decimal(amount["cost_per_verified_record"]) == Decimal(known) / verified
    assert (amount["cost_usd"] is None) == bool(unpriced)


@pytest.mark.parametrize("known,unpriced,verified", [
    ("0", True, True), ("6", True, True),
    ("6", False, True), ("0", False, True), ("6", False, False),
])
def test_memory_summary_keeps_incomplete_cost_unknown(known, unpriced, verified):
    identity = uuid.UUID(int=3)
    at = "2026-10-30T17:00:00+00:00"
    result = {"record_id": identity, "state": "DC", "checked_at": at,
              "fields": {name: {"verified": verified if name == "website" else False}
                         for name in ("website", "email", "phone", "socials")}}
    ledger = [{"id": uuid.UUID(int=4), "record_id": identity, "ts": at,
               "rung": 1, "cost_usd": Decimal(known), "cost_status": "set"}]
    if unpriced:
        ledger.append({"id": uuid.UUID(int=5), "record_id": identity, "ts": at,
                       "rung": 1, "cost_usd": None, "cost_status": "not_set"})
    amount = cost_rows([result], ledger)[0]
    assert Decimal(amount["known_cost_usd"]) == Decimal(known)
    if unpriced or not verified:
        assert amount["cost_per_verified_record"] is None
    else:
        assert Decimal(amount["cost_per_verified_record"]) == Decimal(known)
    assert (amount["cost_usd"] is None) == unpriced
