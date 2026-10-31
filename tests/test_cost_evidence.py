"""Cost evidence: offline ranking and choice, plus a real-SQL batch replay with a stubbed LiteLLM."""
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

import bench
import cost_evidence as ce
from gold import PLATFORM_TENANT
from test_tank_batch_providers import LiteLLMStub, NATIVE
from test_tank_tenant_boundaries import boundary  # noqa: F401
from test_tank_ladder import ladder  # noqa: F401

SYSTEM = {"role": "system", "content": "Long fixed policy prompt " * 20}


def row(task, user, content="plain text", *, system=SYSTEM, cost=0.01, model="astra"):
    return {"task_type": task, "model": model, "cost_usd": cost, "tokens_in": 500,
            "messages": json.dumps([system, {"role": "user", "content": user}]), "content": content}


def test_fixed_prefix_drops_only_the_final_user_turn():
    turns = [SYSTEM, {"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}, {"role": "user", "content": "c"}]
    assert ce.fixed_prefix(turns) == turns[:3]
    assert ce.fixed_prefix([SYSTEM]) == [SYSTEM]


def test_rank_repeats_classifies_and_orders_by_movable_spend():
    rows = [row("zenas.rule_card", f"rule {i % 20}") for i in range(40)]  # half are exact repeats
    rows += [row("zenas.apply", f"element {i}", json.dumps({"applies": True, "why": str(i)}), cost=0.02) for i in range(40)]
    rows += [row("command.turn", f"turn {i}") for i in range(40)]
    rows += [row("tiger.rare", f"x {i}", system={"role": "system", "content": str(i)}) for i in range(40)]
    rows += [row("tiny.task", "same") for _ in range(5)]
    ranked = {r["task_type"]: r for r in ce.rank_repeats(rows)}
    assert ranked["zenas.rule_card"]["exact_repeat_share"] == 0.5
    assert ranked["zenas.rule_card"]["verdict"] == "semantic cache (rung 4)"
    assert ranked["zenas.apply"]["verdict"] == "Skala code skill (rung 3)"
    assert ranked["command.turn"]["verdict"] == "prompt caching only"
    assert ranked["command.turn"]["shared_prefix_share"] == 1.0
    assert ranked["tiger.rare"]["verdict"] == "no repeat signal"
    assert ranked["tiny.task"]["verdict"] == "too few calls" and ranked["tiny.task"]["graduation_value_usd"] == 0
    order = [r["task_type"] for r in ce.rank_repeats(rows)]
    assert order[:2] == ["zenas.apply", "zenas.rule_card"]  # $0.80 movable beats $0.20
    # Aggregates only: no prompt or answer text leaves the tool.
    assert "element 1" not in json.dumps(ce.rank_repeats(rows))


def test_cheapest_passing_needs_serving_score_and_uses_latest_complete_run():
    now = datetime.now(timezone.utc)
    run = lambda i, task, model, score, cost, status="complete", age=0: {
        "id": f"00000000-0000-0000-0000-{i:012d}", "task_type": task, "model": model, "score": score,
        "cost_per_call": cost, "expected_n": 30, "status": status, "finished_at": now - timedelta(hours=age)}
    runs = [run(1, "zenas.scope", "astra", .90, .05), run(2, "zenas.scope", "luna", .95, .0005, age=5),
            run(3, "zenas.scope", "luna", .80, .0005, age=1),  # newer and worse: luna now fails
            run(4, "zenas.scope", "sol", .91, .01), run(5, "zenas.scope", "haiku", .99, .0004, status="failed"),
            run(6, "base.extract", "luna", .99, .0005)]
    policies = [{"task_type": "zenas.scope", "model": "astra", "rung": 1},
                {"task_type": "base.extract", "model": "astra", "rung": 1},
                {"task_type": "zenas.draft", "model": "astra", "rung": 1}]
    report = {r["task_type"]: r for r in ce.cheapest_passing(policies, runs, {"astra": {"input_per_m": 10, "output_per_m": 50}})}
    assert report["zenas.scope"]["cheapest"] == "sol" and report["zenas.scope"]["serving_score"] == .90
    assert report["zenas.scope"]["serving_price"] == {"input_per_m": 10, "output_per_m": 50}
    assert report["base.extract"]["cheapest"] is None and "serving model astra" in report["base.extract"]["missing"]
    assert report["zenas.draft"]["missing"] == "no complete bench run for this task"


def test_replay_policy_turns_off_every_side_path():
    plan = ce.replay_policy({"model": "astra", "semantic_cache": True, "cache_scope": "tenant", "shadow_rate": .1,
                             "candidate_model": "luna", "routellm_weak_model": "luna", "routellm_threshold": .5,
                             "moa_enabled": True, "max_tokens_out": 99}, "luna")
    assert plan == {"model": "luna", "semantic_cache": False, "cache_scope": "none", "shadow_rate": 0,
                    "candidate_model": None, "routellm_weak_model": None, "routellm_threshold": None,
                    "moa_enabled": False, "max_tokens_out": 99}


@pytest.mark.asyncio
async def test_replay_runs_the_eval_suite_through_one_half_price_batch_and_records_a_bench_run(ladder, monkeypatch):  # noqa: F811
    b = ladder
    async def roster():
        return [{'model_name': 'batch-fixture', 'litellm_params': {'model': 'openai/' + NATIVE['openai']},
                 'model_info': {'input_cost_per_token': 0.000002, 'output_cost_per_token': 0.00001}},
                {'model_name': 'sync-only', 'litellm_params': {'model': 'deepseek/deepseek-chat'},
                 'model_info': {'input_cost_per_token': 0.000001, 'output_cost_per_token': 0.000002}}]
    monkeypatch.setattr(b.tank, '_roster_models', roster)
    monkeypatch.setattr(bench, 'runtime', lambda: b.tank)
    stub = LiteLLMStub('openai')
    monkeypatch.setattr(b.tank, '_batch_gateway', stub)
    async with b.pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.policy SELECT (jsonb_populate_record(NULL::tank.policy, to_jsonb(p)||
            '{"task_type":"replay.fixture","model":"sync-only","rung":1,"max_cost_usd":1,"semantic_cache":true}'::jsonb)).*
            FROM tank.policy p WHERE task_type='base.normalize' AND tenant_id IS NULL""")
        for i, expected in enumerate(["Offline answer", "Offline answer", "Something else"]):
            await conn.execute("INSERT INTO tank.evals(task_type,input,expected) VALUES('replay.fixture',$1,$2)",
                               json.dumps(f"Offline input {i}"), json.dumps(expected))

    assert (await ce.replay(b.tank, 'replay.fixture', 'sync-only'))['status'] == 'refused'
    assert (await ce.replay(b.tank, 'replay.fixture', 'batch-fixture', cap_usd=Decimal(0)))['status'] == 'refused'
    assert (await ce.replay(b.tank, 'missing.task', 'batch-fixture'))['reason'] == 'no platform policy for this task'
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.evals SET verdict='rejected' WHERE task_type='replay.fixture'")
    assert (await ce.replay(b.tank, 'replay.fixture', 'batch-fixture'))['reason'].startswith('no platform evals')
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.evals SET verdict='accepted' WHERE task_type='replay.fixture'")
    queued = await ce.replay(b.tank, 'replay.fixture', 'batch-fixture')
    assert queued['status'] == 'queued' and queued['cases'] == 3
    assert (await ce.replay(b.tank, 'replay.fixture', 'batch-fixture'))['batch_id'] == queued['batch_id']  # same day: idempotent
    batch_id = __import__('uuid').UUID(queued['batch_id'])
    assert (await ce.score(b.tank, 'replay.fixture', 'batch-fixture', batch_id))['status'] == 'pending'

    await b.tank.process_batches_once()
    assert len(stub.submissions()) == 1 and len(stub.rows) == 3
    stub.finished = True
    await b.tank.process_batches_once()
    await b.tank.process_batches_once()
    assert (await ce.score(b.tank, 'replay.fixture', 'sync-only', batch_id))['status'] == 'refused'
    scored = await ce.score(b.tank, 'replay.fixture', 'batch-fixture', batch_id)
    assert scored['status'] == 'complete' and scored['n'] == 3 and scored['recorded']
    assert scored['score'] == pytest.approx(2 / 3)
    # Evidence is priced as a live call so it compares with the synchronous bench; the batch paid half.
    assert scored['cost_per_call'] == pytest.approx(0.0007)
    assert scored['batch_cost_per_call'] == pytest.approx(0.00035)
    assert (await ce.score(b.tank, 'replay.fixture', 'batch-fixture', batch_id))['recorded'] is False
    async with b.pool.acquire() as conn:
        runs = await conn.fetch("SELECT * FROM tank.bench_runs WHERE task_type='replay.fixture'")
        assert len(runs) == 1 and runs[0]['comparison_model'] == 'sync-only' and runs[0]['tenant_id'] == PLATFORM_TENANT
        evidence = await conn.fetchrow("SELECT * FROM tank.route_evidence WHERE task_type='replay.fixture' AND model='batch-fixture'")
        assert evidence['bench_n'] == 3 and float(evidence['bench_score']) == pytest.approx(2 / 3)
        ledger = await conn.fetch("SELECT * FROM tank.ledger WHERE task_type='replay.fixture'")
        assert len(ledger) == 3 and all(r['agent'] == 'bench' and r['batch'] and r['model'] == 'batch-fixture'
                                        and r['tenant_id'] == PLATFORM_TENANT for r in ledger)
        # The serving route is untouched and no candidate answer reaches the semantic cache.
        assert await conn.fetchval("SELECT model FROM tank.policy WHERE task_type='replay.fixture' AND tenant_id IS NULL") == 'sync-only'
        if await conn.fetchval("SELECT to_regclass('tank.semantic_cache')"):
            assert not await conn.fetchval("SELECT count(*) FROM tank.semantic_cache WHERE task_type='replay.fixture'")
