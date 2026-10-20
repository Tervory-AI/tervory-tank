"""One bad batch stays out of the pool, the gold set, and a shared model."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

import gold
import graduate
import training
from gold import PLATFORM_TENANT
from test_train1 import database as _database

database = _database
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
sys.path.insert(0, str(ROOT / "agents" / "market_lab"))

from core.batch_guard import Pool  # noqa: E402
from feeds.db import apply_schema, connect  # noqa: E402
from feeds.store import Store  # noqa: E402

TENANT = "00000000-0000-0000-0000-000000000001"


def _train():
    spec = importlib.util.spec_from_file_location("batch_guard_train", ROOT / "jobs" / "train" / "train.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _point(date: str, value: str, batch_id: str, **extra: str) -> dict:
    row = {
        "date": date,
        "value": value,
        "source": "fixture",
        "fetched_at": "2026-02-01T00:00:00Z",
        "region": "za",
        "currency": "ZAR",
        "unit": "rand",
        "batch_id": batch_id,
    }
    row.update(extra)
    return row


def test_view_copy_holds_rejected_batches_out_of_the_pool() -> None:
    result = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--import",
            str(ROOT / "tests" / "market_lab_register.mjs"),
            "--test",
            str(ROOT / "tests" / "batch_guard_view.test.ts"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_rand_jump_is_held_and_keeps_provenance() -> None:
    pool = Pool()
    pool.ensure_series("zar.rand", tenant_id=TENANT, unit="rand", source="fixture", currency="ZAR", region="za")
    opened = pool.ingest( "zar.rand", TENANT, [_point("2026-01-01", "18.50", "batch-ok")])
    assert opened["status"] == "pooled"
    stored = pool.pooled(TENANT, "zar.rand")
    assert len(stored) == 1
    for name in ("source", "fetched_at", "region", "currency", "unit", "batch_id"):
        assert stored[0][name]
    assert stored[0]["currency"] == "ZAR" and stored[0]["unit"] == "rand" and stored[0]["region"] == "za"
    held = pool.ingest("zar.rand", TENANT, [_point("2026-02-01", "18500", "batch-spike")])
    assert held["status"] == "held"
    assert "change is beyond the series limit" in held["reason"]
    assert [point["batch_id"] for point in pool.pooled(TENANT, "zar.rand")] == ["batch-ok"]
    assert pool.held(TENANT)[0]["id"] == "batch-spike"


def test_unit_currency_official_and_limit_hold_the_batch() -> None:
    pool = Pool()
    pool.ensure_series(
        "zar.rand",
        tenant_id=TENANT,
        unit="rand",
        source="fixture",
        currency="ZAR",
        region="za",
        jump_limit="2",
        official={"2026-03-01": "20"},
    )
    pool.ingest("zar.rand", TENANT, [_point("2026-01-01", "18.50", "batch-ok")])
    mismatch = pool.ingest("zar.rand", TENANT, [_point("2026-02-01", "19", "batch-unit", unit="dollar", currency="USD")])
    assert mismatch["status"] == "held"
    assert "unit does not match" in mismatch["reason"]
    assert "currency does not match" in mismatch["reason"]
    limited = pool.ingest("zar.rand", TENANT, [_point("2026-02-01", "40", "batch-limit")])
    assert limited["status"] == "held"
    assert "change is beyond the series limit" in limited["reason"]
    official = pool.ingest("zar.rand", TENANT, [_point("2026-03-01", "21", "batch-official")])
    assert official["status"] == "held"
    assert "official" in official["reason"]
    assert len(pool.pooled(TENANT, "zar.rand")) == 1


def test_reject_never_enters_and_remove_drops_the_pool() -> None:
    pool = Pool()
    pool.ensure_series("zar.rand", tenant_id=TENANT, unit="rand", source="fixture", currency="ZAR", region="za")
    pool.ingest("zar.rand", TENANT, [_point("2026-01-01", "18.50", "batch-ok")])
    pool.ingest("zar.rand", TENANT, [_point("2026-02-01", "18500", "batch-spike")])
    assert pool.reject(TENANT, "batch-spike")["status"] == "rejected"
    with pytest.raises(RuntimeError):
        pool.release(TENANT, "batch-spike")
    assert [point["batch_id"] for point in pool.pooled(TENANT)] == ["batch-ok"]
    assert pool.remove(TENANT, "batch-ok")["status"] == "removed"
    assert pool.pooled(TENANT) == []
    rows = gold.retire_gold_rows(
        [
            {"batch_id": "batch-ok", "status": "checked"},
            {"batch_id": "batch-other", "status": "checked"},
        ],
        "batch-ok",
    )
    assert rows[0]["status"] == "rejected" and rows[0]["note"] == "Batch removed"
    assert rows[1]["status"] == "checked"


def test_sqlite_rand_series_is_held_out_of_points(tmp_path: Path) -> None:
    conn = connect("sqlite:///" + str(tmp_path / "feeds.sqlite"))
    apply_schema(conn)
    store = Store(conn)
    series_id = store.ensure_series("fx", "rand", "Rand series", "rand", "national", "ZA", "monthly")
    conn.execute("UPDATE series SET currency = ?, region = ? WHERE id = ?", ("ZAR", "za", series_id))
    assert store.put_point(series_id, "2026-01-01", "18.50", "r1") is True
    assert store.put_point(series_id, "2026-02-01", "18500", "r1") is False
    pooled = conn.execute("SELECT value, source_id, region, currency, unit, batch_id, fetched_at FROM points").fetchall()
    assert len(pooled) == 1
    assert Decimal(str(pooled[0]["value"])) == Decimal("18.50")
    for name in ("source_id", "region", "currency", "unit", "batch_id", "fetched_at"):
        assert pooled[0][name]
    held = store.held_batches()
    assert len(held) == 1 and held[0]["status"] == "held"
    assert "change is beyond the series limit" in held[0]["reason"]
    store.reject_batch(held[0]["id"])
    assert conn.execute("SELECT count(*) FROM points").fetchone()[0] == 1
    with pytest.raises(RuntimeError):
        store.release_batch(held[0]["id"])


def test_training_waits_for_spot_check_quarantine_and_labels() -> None:
    held = {
        "agent": "market_lab",
        "skill_id": "market.series_fetch",
        "region": "za",
        "quarantine": "held",
        "batch_id": "batch-spike",
        "currency": "ZAR",
        "unit": "rand",
        "status": "checked",
        "input": {"value": "18500", "date": "2026-02-01", "unit": "rand", "currency": "ZAR"},
        "expected": {"value": "18500", "unit": "rand", "currency": "ZAR"},
    }
    assert training.admits_training(held) is False
    assert training.admits_training({**held, "quarantine": "passed"}) is True
    assert training.admits_training({"agent": "base", "skill_id": "base.fixture", "input": {"n": 1}, "expected": {"ok": True}})
    price = {"agent": "base", "skill_id": "base.fixture", "input": {"price": 12}, "expected": {"ok": True}}
    assert training.admits_training(price) is False
    assert training.admits_training({**price, "currency": "USD", "unit": "dollar"}) is True


@pytest.mark.asyncio
async def test_spot_check_still_blocks_an_unapproved_market_row(monkeypatch) -> None:
    monkeypatch.setattr(training, "runtime", lambda: SimpleNamespace(box_region=lambda: "us-east"))

    class Recorder:
        def __init__(self) -> None:
            self.calls: list[tuple] = []

        async def execute(self, *args: object) -> None:
            self.calls.append(args)

    row = {
        "holdout": False,
        "auto_label": True,
        "auto_approved": False,
        "agent": "market_lab",
        "skill_id": "market.series_fetch",
        "region": "za",
        "quarantine": "passed",
        "batch_id": "batch-ok",
        "currency": "ZAR",
        "unit": "rand",
        "status": "checked",
        "tenant_id": PLATFORM_TENANT,
        "input": {"value": "18.50", "date": "2026-01-01", "unit": "rand"},
        "expected": {"value": "18.50", "unit": "rand"},
        "checked_by": "founder",
        "id": uuid.uuid4(),
        "public": True,
    }
    conn = Recorder()
    await training.pair_from_gold(conn, row)
    assert conn.calls == []
    await training.pair_from_gold(conn, {**row, "auto_approved": True, "quarantine": "held"})
    assert conn.calls == []
    await training.pair_from_gold(conn, {**row, "auto_approved": True})
    assert conn.calls


def test_shared_rows_keep_region_and_batch_and_reject_an_unlabelled_price() -> None:
    module = _train()
    us = {
        "public": True,
        "client_matter": False,
        "scope": "platform",
        "region": "us-east",
        "holdout": False,
        "active": True,
        "task_type": "market.series_fetch",
        "batch_id": "batch-us",
        "currency": "USD",
        "unit": "dollar",
        "input": {"value": 3, "date": "2026-01-01", "currency": "USD", "unit": "dollar"},
        "output": {"value": 3, "currency": "USD", "unit": "dollar"},
    }
    za = {
        **us,
        "region": "za",
        "batch_id": "batch-za",
        "currency": "ZAR",
        "unit": "rand",
        "input": {"value": "18.50", "date": "2026-01-01", "currency": "ZAR", "unit": "rand"},
        "output": {"value": "18.50", "currency": "ZAR", "unit": "rand"},
    }
    rows = module.shared_rows([[us], [za]])
    assert [(row["region"], row["batch_id"]) for row in rows] == [("us-east", "batch-us"), ("za", "batch-za")]
    bare = {**us, "currency": "", "unit": "", "batch_id": "", "input": {"price": 18500}, "output": {}}
    with pytest.raises(ValueError):
        module.validate_rows([bare])


def test_one_region_drop_blocks_and_both_regions_allow() -> None:
    def score(region: str, model: str, value: float) -> dict:
        return {
            "region": region,
            "task_type": "fixture.task",
            "skill_id": "fixture.task",
            "candidate_model": model,
            "score": value,
            "final_check": True,
            "version": "1",
        }

    scores = [
        score("us-east", "next", 0.99),
        score("za", "next", 0.80),
        score("us-east", "current", 0.90),
        score("za", "current", 0.95),
    ]
    blocked = graduate.promotion_block(
        candidate="next", current_model="current", skills={"fixture.task"}, scores=scores, removed_models=set()
    )
    assert blocked == "dropped"
    scores[1]["score"] = 0.95
    assert graduate.promotion_block(
        candidate="next", current_model="current", skills={"fixture.task"}, scores=scores, removed_models=set()
    ) is None
    missing_current = [score("us-east", "next", 0.99), score("za", "next", 0.99)]
    assert graduate.promotion_block(
        candidate="next", current_model="current", skills={"fixture.task"}, scores=missing_current, removed_models=set()
    ) is None
    assert graduate.promotion_block(
        candidate="next", current_model="current", skills={"fixture.task"}, scores=[score("us-east", "next", 0.99)], removed_models=set()
    ) == "missing held-out score"
    assert graduate.promotion_block(
        candidate="owned-a", current_model="current", skills={"fixture.task"}, scores=scores, removed_models={"owned-a"}
    ) == "trained on removed data"


def test_schema_adds_lineage_without_dropping() -> None:
    added = (ROOT / "tank" / "schema.sql").read_text(encoding="utf-8").split("-- A training row keeps the batch", 1)[1]
    for name in ("batch_id", "removed_batches", "training_job_batches", "training_snapshot_batches"):
        assert name in added
    assert "DROP " not in added.upper()
    agent = (ROOT / "agents" / "market_lab" / "schema.sql").read_text(encoding="utf-8").lower()
    assert "batch_id" in agent and "update " not in agent
    feeds = (ROOT / "agents" / "market_lab" / "feeds" / "schema.sql").read_text(encoding="utf-8")
    for name in ("source_id", "fetched_at", "region", "currency", "unit", "batch_id"):
        assert name in feeds


@pytest.mark.asyncio
async def test_quarantine_route_requires_the_room_key(monkeypatch) -> None:
    import httpx

    monkeypatch.setenv("TANK_KEY", "room-key")
    spec = importlib.util.spec_from_file_location("market_lab_quarantine_app", ROOT / "agents" / "market_lab" / "app.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    app = module.app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        denied = await client.get("/quarantine")
        allowed = await client.get("/quarantine", headers={"X-Tank-Key": "room-key"})
    assert denied.status_code == 401
    assert allowed.status_code in (200, 503)


@pytest.mark.asyncio
async def test_removed_batch_marks_every_model_trained_on_it(database) -> None:
    pool, _ = database
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO tank.policy(task_type,model,candidate_model,auto_promote)
            VALUES ('fixture.removed','current','owned-a',false)"""
        )
        await conn.execute(
            """INSERT INTO tank.graduation_rank(task_type,candidate,kind)
            VALUES ('fixture.removed','owned-a','owned')"""
        )
        await conn.execute(
            """INSERT INTO tank.gold_examples
            (tenant_id,region,skill_id,agent,input,expected,source,source_ref,input_hash,status,batch_id)
            SELECT $1,'us-east','fixture.removed','base','{}','{}','package',
            'kept-' || number::text,number::text,'checked','batch-kept' FROM generate_series(1,100) number""",
            PLATFORM_TENANT,
        )
        await conn.execute(
            """INSERT INTO tank.gold_examples
            (tenant_id,region,skill_id,agent,input,expected,source,source_ref,input_hash,status,batch_id)
            VALUES ($1,'za','market.series_fetch','market_lab','{}','{}','room_auto','removed-row','removed-hash','checked','batch-removed')""",
            PLATFORM_TENANT,
        )
        for region in ("us-east", "za"):
            await conn.execute(
                """INSERT INTO tank.gold_scores
                (tenant_id,region,skill_id,version,task_type,candidate_model,score,n,final_check,cost_per_call)
                VALUES ($1,$2,'fixture.removed','1','fixture.removed','owned-a',.99,20,true,0)""",
                PLATFORM_TENANT,
                region,
            )
        await conn.execute(
            """INSERT INTO tank.training_job_batches (tenant_id,job_id,model_repo,batch_id,region)
            VALUES ($1,'job-1','owned-a','batch-removed','za'),
                   ($1,'job-2','owned-b','batch-removed','us-east')""",
            PLATFORM_TENANT,
        )
        models = await training.retire_batch(conn, PLATFORM_TENANT, "batch-removed")
        assert models == ["owned-a", "owned-b"]
        assert await conn.fetchval(
            "SELECT status FROM tank.gold_examples WHERE batch_id='batch-removed'"
        ) == "rejected"
        assert await conn.fetchval(
            "SELECT status FROM tank.gold_examples WHERE batch_id='batch-kept' LIMIT 1"
        ) == "checked"
        row = next(item for item in await graduate.training_table(conn, PLATFORM_TENANT, "us-east") if item["task_type"] == "fixture.removed")
        assert row["trained_on_removed"] is True
        assert row["can_promote"] is False
        assert row["blocked_reason"] == "trained on removed data"


@pytest.mark.asyncio
async def test_training_table_blocks_a_drop_in_only_one_region(database) -> None:
    pool, _ = database
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO tank.policy(task_type,model,candidate_model,auto_promote)
            VALUES ('fixture.regions','current','next',false)"""
        )
        await conn.execute(
            """INSERT INTO tank.graduation_rank(task_type,candidate,kind)
            VALUES ('fixture.regions','next','model')"""
        )
        await conn.execute(
            """INSERT INTO tank.gold_examples
            (tenant_id,region,skill_id,agent,input,expected,source,source_ref,input_hash,status)
            SELECT $1,'us-east','fixture.regions','base','{}','{}','package',
            number::text,number::text,'checked' FROM generate_series(1,100) number""",
            PLATFORM_TENANT,
        )
        await conn.execute(
            """INSERT INTO tank.ledger(tenant_id,region,agent,task_type,model,cost_usd)
            VALUES ($1,'us-east','base','fixture.regions','current',.02)""",
            PLATFORM_TENANT,
        )
        pairs = (("us-east", "next", 0.99), ("za", "next", 0.80), ("us-east", "current", 0.90), ("za", "current", 0.95))
        for region, model, score in pairs:
            await conn.execute(
                """INSERT INTO tank.gold_scores
                (tenant_id,region,skill_id,version,task_type,candidate_model,score,n,final_check,cost_per_call)
                VALUES ($1,$2,'fixture.regions','1','fixture.regions',$3,$4,20,true,.01)""",
                PLATFORM_TENANT,
                region,
                model,
                score,
            )
        row = next(item for item in await graduate.training_table(conn, PLATFORM_TENANT, "us-east") if item["task_type"] == "fixture.regions")
        assert row["heldout_score"] == 0.99
        assert row["heldout_by_region"]["us-east"] == 0.99
        assert row["heldout_by_region"]["za"] == 0.80
        assert row["can_promote"] is False
        assert row["blocked_reason"] == "dropped"
        await conn.execute(
            """UPDATE tank.gold_scores SET score=.96
            WHERE task_type='fixture.regions' AND region='za' AND candidate_model='next'"""
        )
        again = next(item for item in await graduate.training_table(conn, PLATFORM_TENANT, "us-east") if item["task_type"] == "fixture.regions")
        assert again["can_promote"] is True
        assert again["blocked_reason"] is None
