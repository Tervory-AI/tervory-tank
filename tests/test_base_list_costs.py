"""B8: list ledger arithmetic, tenant-scoped reads and trailing CSV costs."""
import csv
import io
import json
import subprocess
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import base_lists as lists
import base_metrics as metrics
import command
import httpx
import pytest
from fastapi import FastAPI
from test_base_database import database  # noqa: F401 -- isolated, rolled-back local fixture
from test_base_lists import OTHER, RECORD, TENANT, Pool, record

ROOT = Path(__file__).resolve().parents[1]


def entry(**changes):
    return {"id": uuid4(), "record_id": str(RECORD), "cost_usd": Decimal("0.10000001"),
            "baseline_cost_usd": Decimal("0.30000003"), "cost_status": "set", **changes}


def test_exact_decimal_totals_deduplicate_ledger_ids_across_links():
    one, two = entry(), entry(cost_usd=Decimal("0.20000002"), baseline_cost_usd=Decimal("0.40000004"))
    rows = [one, deepcopy(one), two, {**one, "record_id": str(uuid4())}]
    assert metrics.list_costs(rows) == {"actual_usd": Decimal("0.30000003"), "baseline_usd": Decimal("0.70000007"),
                                      "saved_usd": Decimal("0.40000004"), "calls": 2, "receipt_status": "priced"}
    assert metrics.list_costs([]) == {"actual_usd": None, "baseline_usd": None,
                                    "saved_usd": None, "calls": 0, "receipt_status": "price not set"}


@pytest.mark.parametrize("changes", [{"cost_status": "not_set"}, {"cost_usd": None}])
def test_unknown_actual_price_never_becomes_zero_or_a_saving(changes):
    costs = metrics.list_costs([entry(), entry(**changes)])
    assert costs["actual_usd"] is None and costs["saved_usd"] is None
    assert costs["baseline_usd"] == Decimal("0.60000006")
    assert costs["calls"] == 2 and costs["receipt_status"] == "price not set"


def test_unknown_baseline_preserves_actual_but_has_no_baseline_or_saving():
    costs = metrics.list_costs([entry(), entry(baseline_cost_usd=None)])
    assert costs == {"actual_usd": Decimal("0.20000002"), "baseline_usd": None,
                     "saved_usd": None, "calls": 2, "receipt_status": "priced"}


def test_only_list_csv_appends_costs_and_keeps_all_existing_columns_and_cells():
    first, second = record(), record()
    second["record_id"] = str(uuid4())
    one = entry()
    two = entry(record_id=second["record_id"], cost_status="not_set", baseline_cost_usd=None)
    ledger = [one, deepcopy(one), two, entry(record_id=str(uuid4()), cost_usd=999)]
    old = list(csv.reader(io.StringIO(metrics.export_records([first, second]).lstrip("\ufeff"))))
    content = metrics.export_records([first, second], ledger=ledger)
    new = list(csv.reader(io.StringIO(content.lstrip("\ufeff"))))
    assert content.startswith("\ufeff") and "\r\n" in content
    assert new[0] == old[0] + ["cost_usd", "baseline_cost_usd"]
    assert [row[:-2] for row in new] == old
    assert new[1][-2:] == ["0.10000001", "0.30000003"]
    assert new[2][-2:] == ["", ""]
    empty = list(csv.reader(io.StringIO(metrics.export_records([first], ledger=[]).lstrip("\ufeff"))))
    assert empty[1][-2:] == ["", ""]
    assert next(csv.reader(io.StringIO(metrics.export_records([first]).lstrip("\ufeff")))) == old[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("unknown", [False, True, "missing"])
async def test_show_export_and_csv_share_ledger_totals_and_tenant_scope(monkeypatch, unknown):
    own, foreign = uuid4(), uuid4()
    one = entry(**({"cost_status": "not_set"} if unknown is True else {}))
    records = [record()]
    if unknown == "missing":
        records.append({**record(), "record_id": str(uuid4())})
    class LedgerPool(Pool):
        def __init__(self):
            super().__init__()
            self.reads = []
        async def fetch(self, sql, tenant, ids):
            assert "JOIN tank.base_ledger_links b ON b.tenant_id=$1 AND b.ledger_id=l.id" in sql
            assert "WHERE l.tenant_id=$1 AND l.agent='base' AND b.record_id=ANY($2::uuid[])" in sql
            assert tenant == TENANT and list(map(str, ids)) == [row["record_id"] for row in records]
            self.reads.append((tenant, ids))
            return [one, deepcopy(one)]
    pool = LedgerPool()
    for tenant, key in ((TENANT, own), (OTHER, foreign)):
        pool.saved[tenant, key] = {"name": "placeholder list", "records": json.dumps(records), "filters": "{}"}
    actor = command.Actor(TENANT, "placeholder-user", False, frozenset({"base"}))
    monkeypatch.setattr(command, "db", lambda: pool)
    receipts = []
    async def receipt(tenant, tool):
        assert tenant == TENANT
        receipts.append(tool)
        return str(uuid4())
    monkeypatch.setattr(lists, "receipt", receipt)
    app = FastAPI()
    app.include_router(lists.build_router())
    app.dependency_overrides[command.identity] = lambda: actor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder") as client:
        for path in ("show", "export"):
            response = await client.get("/v1/command/base/lists/" + path, params={"list_id": str(own), "tenant_id": str(OTHER)})
            assert response.status_code == 200
            data = response.json()
            assert data["actual_usd"] == (None if unknown else 0.10000001)
            assert data["baseline_usd"] == (None if unknown == "missing" else 0.30000003)
            assert data["saved_usd"] == (None if unknown else 0.20000002)
            assert data["calls"] == 1
            assert data["receipt_status"] == ("price not set" if unknown else "priced")
            assert "cost_usd" not in data  # Actual list cost uses the existing Cost label once.
            assert data["ledger_id"]
        response = await client.get("/v1/command/base/lists/csv", params={"list_id": str(own)})
        assert response.status_code == 200
        rows = list(csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))))
        assert rows[0]["cost_usd"] == ("" if unknown is True else "0.10000001")
        if unknown == "missing":
            assert rows[1]["cost_usd"] == rows[1]["baseline_cost_usd"] == ""
        assert rows[0]["baseline_cost_usd"] == "0.30000003"
        assert len(pool.reads) == 3
        for path in ("show", "export", "csv"):
            response = await client.get("/v1/command/base/lists/" + path, params={"list_id": str(foreign)})
            assert response.status_code == 404
        assert len(pool.reads) == 3  # A foreign list never reaches the ledger query.
    assert receipts == ["base.list.show", "base.list.export"]


@pytest.mark.asyncio
async def test_real_ledger_join_never_counts_foreign_tenant_links_or_rows(database):  # noqa: F811
    conn, runtime = database
    tenant, other, first, second = (uuid4() for _ in range(4))
    own_id = await conn.fetchval("INSERT INTO tank.ledger(tenant_id,region,agent,task_type,rung,model,cost_usd,tokens_in,tokens_out) "
                                 "VALUES($1,'us-east','base','placeholder.b8',3,'code',0,0,0) RETURNING id", tenant)
    foreign_id = await conn.fetchval("INSERT INTO tank.ledger(tenant_id,region,agent,task_type,rung,model,cost_usd,tokens_in,tokens_out) "
                                     "VALUES($1,'us-east','base','placeholder.b8',3,'code',0,0,0) RETURNING id", other)
    for owner, record_id, ledger_id in ((tenant, first, own_id), (tenant, second, own_id),
                                        (other, first, foreign_id), (tenant, first, foreign_id), (other, second, own_id)):
        await conn.execute("INSERT INTO tank.base_ledger_links(tenant_id,record_id,ledger_id) VALUES($1,$2,$3)", owner, record_id, ledger_id)
    store = lists.Store(runtime.pool())
    rows = await store.ledger(tenant, [{"record_id": str(first)}, {"record_id": str(second)}])
    assert len(rows) == 2 and {row["id"] for row in rows} == {own_id}
    assert {row["tenant_id"] for row in rows} == {tenant}
    assert metrics.list_costs(rows)["calls"] == 1
    assert len(await store.ledger(tenant, [{"record_id": str(first)}])) == 1
    assert await store.ledger(tenant, [{"record_id": str(uuid4())}]) == []
    assert await store.ledger(tenant, []) == []


def test_list_receipt_uses_existing_card_labels_and_download_columns():
    result = subprocess.run(["node", "tests/base_list_costs.cjs"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr



def test_any_record_without_ledger_evidence_makes_list_totals_unknown():
    one = entry()
    assert metrics.list_costs([one], record_ids=[RECORD])["actual_usd"] == Decimal("0.10000001")
    costs = metrics.list_costs([one], record_ids=[RECORD, uuid4()])
    assert costs == {"actual_usd": None, "baseline_usd": None, "saved_usd": None,
                     "calls": 1, "receipt_status": "price not set"}


def test_shared_ledger_rows_leave_both_cost_cells_blank_without_allocating_cost():
    first, second = record(), {**record(), "record_id": str(uuid4())}
    one = entry()
    ledger = [one, deepcopy(one), {**one, "record_id": second["record_id"]}, entry()]
    rows = list(csv.DictReader(io.StringIO(metrics.export_records([first, second], ledger=ledger).lstrip("\ufeff"))))
    assert len(rows) == 2
    assert all(row["cost_usd"] == row["baseline_cost_usd"] == "" for row in rows)
    assert metrics.list_costs(ledger, record_ids=[first["record_id"], second["record_id"]])["calls"] == 2
    own = list(csv.DictReader(io.StringIO(metrics.export_records([first], ledger=ledger).lstrip("\ufeff"))))
    assert own[0]["cost_usd"] == "0.20000002"  # A link outside this list is not shared within it.


def test_csv_costs_always_use_fixed_point_and_preserve_known_zeroes():
    one = entry(cost_usd=Decimal("1E-8"), baseline_cost_usd=Decimal("2E-8"))
    rows = list(csv.DictReader(io.StringIO(metrics.export_records([record()], ledger=[one]).lstrip("\ufeff"))))
    assert rows[0]["cost_usd"] == "0.00000001"
    assert rows[0]["baseline_cost_usd"] == "0.00000002"
    one.update(cost_usd=Decimal("0E-8"), baseline_cost_usd=Decimal("0E-8"))
    rows = list(csv.DictReader(io.StringIO(metrics.export_records([record()], ledger=[one]).lstrip("\ufeff"))))
    assert rows[0]["cost_usd"] == rows[0]["baseline_cost_usd"] == "0.00000000"
