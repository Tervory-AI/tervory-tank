"""No paid requests: provider fixtures exercise routing, evidence and accounting."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import uuid

import httpx
import pytest
from fastapi import FastAPI
import yaml

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import main
import research
import graduate

ROOT = Path(__file__).resolve().parents[1]
TENANT = uuid.UUID("22222222-2222-2222-2222-222222222222")
RATES = {"search_web": Decimal("0.001"), "fetch_url": Decimal("0.0005")}


def response_fixture():
    # Shape retained by LiteLLM 1.106.0 ResponsesAPIResponse; IDs are deliberately
    # out of order, so array positions cannot accidentally masquerade as markers.
    return {
        "status": "completed", "preset": "low@2026-10-16.0",
        "output": [
            {"type": "search_results", "results": [
                {"id": 9, "source": "web", "url": "https://example.org/nine", "title": "Nine"},
                {"id": 2, "source": "web", "url": "https://example.org/two", "title": "Two"},
            ]},
            {"type": "message", "role": "assistant", "content": [
                {"type": "output_text", "text": "A claim [web:2]. Another [web:9][web:2]."},
            ]},
        ],
        "usage": {"input_tokens": 100, "output_tokens": 200, "cost": 0.0067,
                  "tool_calls_details": {"search_web": {"invocation": 2}, "fetch_url": {"invocation": 1}}},
    }


def test_sources_match_returned_ids_and_only_cited_sources_are_returned():
    content, sources = research.answer_sources(response_fixture())
    assert content.startswith("A claim [web:2]")
    assert [(s["marker"], s["url"]) for s in sources] == [
        ("[web:2]", "https://example.org/two"), ("[web:9]", "https://example.org/nine")]


@pytest.mark.parametrize("text", ["No sources", "Invented [web:1]", "Unsupported [file:2]"])
def test_missing_or_invented_markers_fail(text):
    data = response_fixture()
    data["output"][1]["content"][0]["text"] = text
    with pytest.raises(ValueError):
        research.answer_sources(data)


def test_conflicting_source_ids_fail():
    data = response_fixture()
    data["output"].append({"type": "search_results", "results": [
        {"id": 2, "source": "web", "url": "https://example.org/different"}]})
    with pytest.raises(ValueError, match="ambiguous"):
        research.answer_sources(data)


@pytest.mark.parametrize("normalized", [True, False])
def test_reported_total_is_never_double_charged(normalized):
    data = response_fixture()
    if not normalized:
        data["usage"]["cost"] = {"currency": "USD", "total_cost": 0.0067,
                                  "tool_calls_cost": 0.0025}
    costs = research.receipt_costs(data, RATES)
    assert costs["cost_usd"] == Decimal("0.0067")
    assert costs["token_cost_usd"] == Decimal("0.0042")
    assert costs["search_fee_usd"] == Decimal("0.002")
    assert costs["fetch_fee_usd"] == Decimal("0.0005")
    assert sum(line["cost_usd"] for line in costs["lines"]) == costs["cost_usd"]


@pytest.mark.parametrize("fee", ["0.0025000000001", "0.0024999999999", "0.002500001"])
def test_provider_fee_rounding_is_tolerated(fee):
    data = response_fixture()
    data["usage"]["cost"] = {"total_cost": "0.0067", "tool_calls_cost": fee}
    assert research.receipt_costs(data, RATES)["cost_usd"] == Decimal("0.0067")


def test_substantive_provider_fee_mismatch_is_refused():
    data = response_fixture()
    data["usage"]["cost"] = {"total_cost": "0.0067", "tool_calls_cost": "0.002500002"}
    with pytest.raises(ValueError, match="disagree"):
        research.receipt_costs(data, RATES)


@pytest.mark.parametrize("cost", [None, -1, "NaN", "Infinity", True, {}, {"total_cost": 1, "currency": "EUR"}])
def test_absent_or_invalid_cost_is_not_reported_as_free(cost):
    data = response_fixture()
    data["usage"]["cost"] = cost
    with pytest.raises(ValueError):
        research.receipt_costs(data, RATES)


def test_unpriced_tools_are_refused():
    data = response_fixture()
    data["usage"]["tool_calls_details"]["sandbox"] = {"invocation": 1}
    with pytest.raises(ValueError, match="unsupported"):
        research.receipt_costs(data, RATES)


class Connection:
    def __init__(self):
        self.writes = []
        self.price_reads = []
        self.transactions = 0
        self.in_transaction = False
        self.reject_vendor = None

    @asynccontextmanager
    async def transaction(self):
        start = len(self.writes)
        self.transactions += 1
        self.in_transaction = True
        try:
            yield
        except Exception:
            del self.writes[start:]
            raise
        finally:
            self.in_transaction = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def fetch(self, query, *args):
        self.price_reads.append((query, args))
        return [{"outcome_type": research.FEE_TYPES[tool], "unit_price": rate} for tool, rate in RATES.items()]

    async def execute(self, query, *args):
        if "tank.ledger" in query:
            assert self.in_transaction
            if args[3] == self.reject_vendor:
                raise RuntimeError("vendor insert failed")
        self.writes.append((query, args))


@pytest.fixture
def harness(monkeypatch):
    monkeypatch.delenv("TANK_PROVIDER_ALLOW", raising=False)
    monkeypatch.delenv("ZA_HOSTED_MODELS", raising=False)
    monkeypatch.setenv("TANK_KEY_MARKET_LAB", "test-room")
    conn = Connection()
    policy = {"model": "research-low", "promoted_at": datetime.now(timezone.utc),
              "auto_promote": False, "max_tokens_out": 2048, "system_prompt": "Use public sources."}
    seen = []

    async def load(task, tenant):
        assert task == "market.research" and tenant == TENANT
        return policy

    runtime = {"TANK_API_KEY": "test-workspace", "LITELLM_URL": "http://litellm:4000",
               "LITELLM_MASTER_KEY": "test-gateway", "pool": lambda: SimpleNamespace(acquire=lambda: conn),
               "PLATFORM_TENANT": main.PLATFORM_TENANT, "load_policy": load,
               "box_region": lambda: "us-east", "home_region_refusal": main.home_region_refusal,
               "call_home": main.call_home, "model_call_refusal": main.model_call_refusal}
    state = SimpleNamespace(conn=conn, policy=policy, runtime=runtime, seen=seen,
                            data=response_fixture(), code=200, exception=None)

    async def unpaused():
        return False

    monkeypatch.setattr(research.controls, "paid_paused", unpaused)
    monkeypatch.setattr(research.controls, "db", runtime["pool"])

    class Gateway:
        def __init__(self, **_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def post(self, url, **kwargs):
            seen.append((url, kwargs))
            if state.exception:
                raise state.exception
            return httpx.Response(state.code, json=state.data)

    app = FastAPI()
    research.register(app, runtime)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(research.httpx, "AsyncClient", Gateway)
    state.client = lambda: real_client(transport=httpx.ASGITransport(app=app), base_url="http://tank")
    return state


async def call(h, body=None, key="test-room", path="/v1/research"):
    async with h.client() as client:
        return await client.post(path, headers={"X-Tank-Key": key}, json=body or {
            "tenant_id": str(TENANT), "question": "What changed?", "preset": "low"})


@pytest.mark.asyncio
async def test_gateway_only_and_itemized_ledger_receipt(harness):
    result = await call(harness)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["receipt"]["search_fee_usd"] == 0.002
    assert body["receipt"]["token_cost_usd"] == 0.0042
    assert body["receipt"]["cost_usd"] == body["cost_usd"] == 0.0067
    assert body["receipt"]["sources"] == body["sources"]
    url, request = harness.seen[0]
    assert url == "http://litellm:4000/v1/responses"
    assert request["json"]["model"] == "research-low"
    assert request["json"]["fallbacks"] == []
    assert request["json"]["disable_fallbacks"] is True
    assert "models" not in request["json"] and "tools" not in request["json"]
    assert request["headers"] == {"Authorization": "Bearer test-gateway"}
    query, row = harness.conn.writes[0]
    assert "INSERT INTO tank.ledger" in query
    assert row[1] == TENANT
    assert row[6] == Decimal("0.0042")
    assert row[13] == Decimal("0.0067")
    assert row[10:13] == (Decimal("0.0042"), Decimal("0.002"), Decimal("0.0005"))
    assert json.loads(row[14]) == body["sources"]
    assert row[15] == "itemized"
    assert harness.conn.transactions == 1
    assert len(harness.conn.writes) == 3
    search, fetch = [args for _, args in harness.conn.writes[1:]]
    assert search[1] == fetch[1] == TENANT
    assert search[3:7] == ("vendor:perplexity.search", "perplexity.search", Decimal(2), Decimal("0.002"))
    assert fetch[3:7] == ("vendor:perplexity.fetch", "perplexity.fetch", Decimal(1), Decimal("0.0005"))
    assert sum(args[6] for _, args in harness.conn.writes) == row[13]
    assert body["receipt"]["ledger_ids"] == {"model": str(row[0]), "search": str(search[0]), "fetch": str(fetch[0])}
    assert harness.conn.price_reads[0][1][0] == main.PLATFORM_TENANT


@pytest.mark.asyncio
async def test_no_fetch_fee_omits_fetch_row(harness):
    harness.data["usage"]["tool_calls_details"].pop("fetch_url")
    response = await call(harness)
    assert response.status_code == 200
    assert len(harness.conn.writes) == 2
    assert sum(row[6] for _, row in harness.conn.writes) == Decimal("0.0067")
    assert set(response.json()["receipt"]["ledger_ids"]) == {"model", "search"}


@pytest.mark.asyncio
async def test_vendor_insert_failure_rolls_back_entire_charge(harness):
    harness.conn.reject_vendor = "vendor:perplexity.fetch"
    with pytest.raises(RuntimeError, match="vendor insert failed"):
        await call(harness)
    assert harness.conn.transactions == 1
    assert not harness.conn.writes


@pytest.mark.asyncio
async def test_unitemized_cost_keeps_one_total_row(harness):
    harness.data["usage"].pop("tool_calls_details")
    response = await call(harness)
    assert response.status_code == 502
    assert len(harness.conn.writes) == 1
    row = harness.conn.writes[0][1]
    assert row[6] == row[13] == Decimal("0.0067")
    assert row[15] == "unitemized"


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["unpromoted", "automatic", "ordinary", "preset", "region", "allow", "identifier"])
async def test_guards_run_before_network_and_writes(harness, monkeypatch, change):
    body = {"tenant_id": str(TENANT), "question": "Public research", "preset": "low"}
    if change == "unpromoted":
        harness.policy["promoted_at"] = None
    elif change == "automatic":
        harness.policy["auto_promote"] = True
    elif change == "ordinary":
        harness.policy["model"] = "grok-top"
    elif change == "preset":
        body["preset"] = "high"
    elif change == "region":
        body["home_region"] = "za"
    elif change == "allow":
        monkeypatch.setenv("TANK_PROVIDER_ALLOW", json.dumps({str(TENANT): ["luna"]}))
    else:
        harness.runtime["box_region"] = lambda: "za"
        body["question"] = "Call +27 82 123 4567"
    result = await call(harness, body)
    assert result.status_code in {403, 409}
    assert not harness.seen and not harness.conn.writes


@pytest.mark.asyncio
@pytest.mark.parametrize("preset", ["sonar", "xhigh", "openai/gpt-6-luna", "low@unknown"])
async def test_unknown_presets_are_refused(harness, preset):
    result = await call(harness, {"tenant_id": str(TENANT), "question": "Public", "preset": preset})
    assert result.status_code == 422
    assert not harness.seen and not harness.conn.writes


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["", "another-room", "test-homes"])
async def test_other_keys_cannot_use_research(harness, key):
    assert (await call(harness, key=key)).status_code == 401
    assert not harness.seen


@pytest.mark.asyncio
async def test_invalid_evidence_still_books_reported_cost(harness):
    harness.data["output"] = []
    result = await call(harness)
    assert result.status_code == 502
    assert sum(row[6] for _, row in harness.conn.writes) == Decimal("0.0067")
    assert harness.conn.writes[0][1][8] == "failed"


@pytest.mark.asyncio
async def test_founder_paid_pause_blocks_research_and_records_refusal(harness, monkeypatch):
    async def paused():
        return True

    monkeypatch.setattr(research.controls, "paid_paused", paused)
    result = await call(harness)
    assert result.status_code == 503
    assert not harness.seen and not harness.conn.price_reads
    assert len(harness.conn.writes) == 1
    query, args = harness.conn.writes[0]
    assert "tank.control_log" in query and "paid_refused" in query
    assert args[1:] == (research.TASK, "research")


@pytest.mark.asyncio
async def test_network_error_is_redacted_and_cost_explicitly_unknown(harness):
    harness.exception = httpx.ConnectError("do not expose upstream detail")
    result = await call(harness)
    assert result.status_code == 502
    assert "upstream detail" not in result.text
    assert harness.conn.writes[0][1][13] is None
    assert harness.conn.writes[0][1][15] == "unknown"


def test_research_rosters_contain_only_approved_presets_with_sources():
    for filename in ("config.yaml", "config.za.yaml"):
        raw = (ROOT / "litellm" / filename).read_text()
        data = yaml.safe_load(raw)
        entries = {row["model_name"]: row for row in data["model_list"]
                   if row["litellm_params"]["model"].startswith("perplexity/")}
        assert set(entries) == set(research.PRESETS)
        for name, preset in research.PRESETS.items():
            row = entries[name]
            assert row["litellm_params"]["model"] == f"perplexity/preset/{preset}"
            assert row["litellm_params"]["api_key"] == "os.environ/PERPLEXITY_API_KEY"
            assert row["model_info"]["research_only"] is True
            assert row["model_info"]["search_fee_per_request"] == 0.001
        assert "https://docs.perplexity.ai/docs/getting-started/pricing" in raw
        assert "2026-10-21" in raw


@pytest.mark.parametrize("filename", ["config.yaml", "config.za.yaml"])
@pytest.mark.parametrize("sanitized", [False, True])
def test_presets_are_visible_but_excluded_from_generic_candidates(filename, sanitized):
    rows = yaml.safe_load((ROOT / "litellm" / filename).read_text())["model_list"]
    if sanitized:
        rows = [main._roster_row(row) for row in rows]
    assert set(research.PRESETS) <= {row["model_name"] for row in rows}
    quotes = graduate.quotes_from_roster(rows)
    assert {quote.name for quote in quotes} == {
        row["model_name"] for row in rows if row["model_name"] not in research.PRESETS}


@pytest.mark.asyncio
async def test_schema_applies_twice_and_preserves_policy(harness):
    url = os.environ.get("POOL_SCHEMA_DATABASE_URL")
    if not url:
        pytest.skip("CI PostgreSQL service required")
    import asyncpg

    admin = await asyncpg.connect(url)
    name = "models2_" + uuid.uuid4().hex
    await admin.execute(f'CREATE DATABASE "{name}"')
    conn = None
    pool = None
    try:
        database_url = url.rsplit("/", 1)[0] + "/" + name
        conn = await asyncpg.connect(database_url)
        schema = (ROOT / "tank/schema.sql").read_text()
        # Start with the schema that existed before this additive migration.
        await conn.execute(schema.split("-- MODELS-2: provider tool charges", 1)[0])
        before = await conn.fetch("SELECT * FROM tank.policy ORDER BY task_type,tenant_id")
        await conn.execute(schema)
        await conn.execute(schema)
        after = await conn.fetch("SELECT * FROM tank.policy ORDER BY task_type,tenant_id")
        # CORE-2 clears the unused reporting baseline once. Serving/routing
        # policy fields must still be byte-for-byte unchanged by these migrations.
        assert [{**dict(row), "baseline_model": None} for row in before] == [dict(row) for row in after]
        rows = await conn.fetch("SELECT outcome_type,unit_price FROM tank.price_book WHERE tenant_id=$1 AND outcome_type LIKE 'perplexity.%'", main.PLATFORM_TENANT)
        assert {r["outcome_type"]: r["unit_price"] for r in rows} == {
            "perplexity.search.fast": Decimal("0.001"), "perplexity.fetch": Decimal("0.0005")}
        assert len(rows) == 2
        # Exercise the real route transaction against PostgreSQL, including the
        # model/vendor split and rollback if a later fee insert fails.
        pool = await asyncpg.create_pool(database_url, min_size=1, max_size=1)
        harness.runtime["pool"] = lambda: pool
        response = await call(harness)
        assert response.status_code == 200
        ids = [uuid.UUID(value) for value in response.json()["receipt"]["ledger_ids"].values()]
        rows = await conn.fetch("SELECT * FROM tank.ledger WHERE tenant_id=$1 AND id=ANY($2::uuid[])", TENANT, ids)
        by_model = {row["model"]: row for row in rows}
        booked = by_model["research-low"]
        assert booked["search_fee_usd"] == Decimal("0.002")
        assert booked["token_cost_usd"] == Decimal("0.0042")
        assert booked["fetch_fee_usd"] == Decimal("0.0005")
        assert booked["cost_usd"] == Decimal("0.0042")
        assert sum(row["cost_usd"] for row in rows) == booked["provider_cost_usd"] == Decimal("0.0067")
        assert by_model["vendor:perplexity.search"]["units"] == 2
        assert by_model["vendor:perplexity.fetch"]["units"] == 1
        assert json.loads(booked["research_sources"]) == response.json()["sources"]
        await conn.execute("""CREATE FUNCTION reject_fetch() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.model = 'vendor:perplexity.fetch' THEN
                    RAISE EXCEPTION 'fixture fetch insert failed';
                END IF;
                RETURN NEW;
            END; $$;
            CREATE TRIGGER reject_fetch BEFORE INSERT ON tank.ledger
            FOR EACH ROW EXECUTE FUNCTION reject_fetch();""")
        before_count = await conn.fetchval("SELECT count(*) FROM tank.ledger WHERE tenant_id=$1", TENANT)
        with pytest.raises(asyncpg.RaiseError, match="fixture fetch insert failed"):
            await call(harness)
        assert await conn.fetchval("SELECT count(*) FROM tank.ledger WHERE tenant_id=$1", TENANT) == before_count
    finally:
        if pool:
            await pool.close()
        if conn:
            await conn.close()
        await admin.execute(f'DROP DATABASE "{name}"')
        await admin.close()


@pytest.mark.asyncio
async def test_market_lab_adapter_waits_for_promotion_and_preserves_receipt(monkeypatch):
    path = ROOT / "agents/market_lab/core/research_adapter.py"
    spec = importlib.util.spec_from_file_location("models2_market_research", path)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    monkeypatch.setenv("TANK_KEY", "test-room")
    calls = []
    enabled = False
    result = {"content": "Answer [web:2]", "sources": [{"marker": "[web:2]", "url": "https://example.org"}],
              "receipt": {"search_fee_usd": 0.001}, "ledger_id": "receipt", "cost_usd": 0.002}

    class Client:
        def __init__(self, **_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def post(self, url, **kwargs):
            calls.append(url)
            assert kwargs["headers"] == {"X-Tank-Key": "test-room"}
            if url.endswith("/status"):
                return httpx.Response(200 if enabled else 409, json={"enabled": enabled})
            return httpx.Response(200, json=copy.deepcopy(result))

    monkeypatch.setattr(adapter.httpx, "AsyncClient", Client)
    assert await adapter.research_if_promoted(str(TENANT), "Question") is None
    assert len(calls) == 1 and calls[0].endswith("/status")
    enabled = True
    answer = await adapter.research_if_promoted(str(TENANT), "Question")
    assert answer["receipt"] == result["receipt"] and answer["citations"] == result["sources"]
    assert len(calls) == 3
