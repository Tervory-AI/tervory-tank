"""Provider prompt caching on rung-1 calls: config, stable prefix and receipts.

No provider key and no paid call: LiteLLM is a stub. The SQL receipt test uses
the shared isolated Postgres fixture and skips without POOL_SCHEMA_DATABASE_URL.
"""
import json
import os
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import yaml

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import batch_providers  # noqa: E402
import prompt_cache  # noqa: E402
from test_tank_tenant_boundaries import boundary  # noqa: F401,E402 -- shared isolated Postgres fixture
from test_tank_ladder import ladder, policy, request  # noqa: F401,E402

ROOT = Path(__file__).resolve().parent.parent
CONFIGS = [ROOT / "litellm" / "config.yaml", ROOT / "litellm" / "config.za.yaml"]
# USD per MTok (cache read, 5-minute cache write), from the provider pricing pages cited in the config.
CACHE_RATES = {
    "openai/gpt-6-luna": (0.01, 0.125), "openai/gpt-6-sol": (0.20, 2.50), "openai/gpt-6-astra": (1.00, 12.50),
    "openai/gpt-6.1-sol": (0.10, 2.50), "anthropic/claude-haiku-5-5": (0.01, 0.125),
    "anthropic/claude-sonnet-5-5": (0.10, 2.50), "anthropic/claude-opus-5-5": (0.20, 5.00),
    "anthropic/claude-fable-5-1": (0.25, 12.50),
}


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.name)
def test_cache_breakpoints_only_on_openai_gpt6_and_anthropic_deployments(path):
    models = yaml.safe_load(path.read_text())["model_list"]
    marked = {m["litellm_params"]["model"] for m in models if "cache_control_injection_points" in m["litellm_params"]}
    # A Gemini or OpenAI-compatible fallback must never receive a cache marker.
    assert marked == set(CACHE_RATES)
    for m in models:
        native = m["litellm_params"]["model"]
        if native not in CACHE_RATES:
            assert "cache_read_input_token_cost" not in (m.get("model_info") or {}), m["model_name"]
            continue
        assert m["litellm_params"]["cache_control_injection_points"] == [{"location": "message", "role": "system"}]
        read, write = CACHE_RATES[native]
        for place in ("model_info", "litellm_params"):
            block = m[place]
            if "input_cost_per_token" not in block:
                continue
            assert block["cache_read_input_token_cost"] == pytest.approx(read / 1e6), (m["model_name"], place)
            assert block["cache_creation_input_token_cost"] == pytest.approx(write / 1e6), (m["model_name"], place)
            # Reads are cheaper than input, 5-minute writes cost 1.25x input.
            assert block["cache_read_input_token_cost"] < block["input_cost_per_token"]
            assert block["cache_creation_input_token_cost"] == pytest.approx(1.25 * block["input_cost_per_token"])


def test_both_regions_carry_the_same_cache_settings():
    def cache_view(path):
        return {m["model_name"]: (m["litellm_params"].get("cache_control_injection_points"),
                                  m["model_info"].get("cache_read_input_token_cost"),
                                  m["model_info"].get("cache_creation_input_token_cost"))
                for m in yaml.safe_load(path.read_text())["model_list"]}
    assert cache_view(CONFIGS[0]) == cache_view(CONFIGS[1])


@pytest.mark.parametrize("usage,expected", [
    ({"prompt_tokens": 2000, "prompt_tokens_details": {"cached_tokens": 1536, "cache_write_tokens": 0}}, (1536, 0)),
    ({"prompt_tokens": 2000, "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 1800}}, (0, 1800)),
    ({"prompt_tokens": 2100, "cache_read_input_tokens": 1024, "cache_creation_input_tokens": 1000,
      "prompt_tokens_details": {"cached_tokens": 1024}}, (1024, 1000)),
    ({"prompt_tokens": 900, "prompt_cache_hit_tokens": 640}, (640, 0)),
    ({"prompt_tokens": 12, "completion_tokens": 6}, (0, 0)),
    ({"prompt_tokens": 10, "prompt_tokens_details": {"cached_tokens": 99}}, (0, 0)),  # impossible total
    ({"prompt_tokens": 10, "prompt_tokens_details": None, "cache_read_input_tokens": "x"}, (0, 0)),
    (None, (0, 0)),
])
def test_cache_tokens_from_every_provider_usage_shape(usage, expected):
    assert prompt_cache.cache_tokens(usage) == expected


def test_fixed_instruction_goes_after_the_policy_prompt():
    convert = {"role": "system", "content": "fixed conversion instruction"}
    with_policy = [{"role": "system", "content": "policy"}, {"role": "user", "content": "judgment"}]
    prompt_cache.insert_fixed(with_policy, True, convert)
    assert [m["content"] for m in with_policy] == ["policy", "fixed conversion instruction", "judgment"]
    bare = [{"role": "user", "content": "judgment"}]
    prompt_cache.insert_fixed(bare, False, convert)
    assert [m["content"] for m in bare] == ["fixed conversion instruction", "judgment"]


def test_run_route_keeps_the_policy_prompt_first_for_case_facts():
    source = (ROOT / "tank" / "main.py").read_text()
    start = source.index('if req.task_type == "zenas.case_facts" and any(')
    block = source[start:start + 600]
    assert 'prompt_cache.insert_fixed(messages, bool(policy["system_prompt"])' in block
    assert "messages.insert(0" not in block


def test_anthropic_batch_marks_the_fixed_system_text_and_books_cache_tokens():
    body = {"model": "claude-sonnet-5-5", "max_tokens": 64, "messages": [
        {"role": "system", "content": "policy"}, {"role": "system", "content": "rule card"},
        {"role": "user", "content": "facts"}]}
    params = batch_providers.anthropic_params(body)
    assert params["system"] == [{"type": "text", "text": "policy"},
                                {"type": "text", "text": "rule card", "cache_control": {"type": "ephemeral"}}]
    assert params["messages"] == [{"role": "user", "content": "facts"}]
    assert "system" not in batch_providers.anthropic_params({**body, "messages": [body["messages"][-1]]})
    row = {"custom_id": "a", "result": {"type": "succeeded", "message": {
        "content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn",
        "usage": {"input_tokens": 50, "output_tokens": 9, "cache_read_input_tokens": 1200,
                  "cache_creation_input_tokens": 300}}}}
    usage = batch_providers.anthropic_result(row)["response"]["body"]["usage"]
    # Anthropic input_tokens excludes cache tokens; the booked prompt total includes them.
    assert usage["prompt_tokens"] == 1550 and usage["completion_tokens"] == 9
    assert prompt_cache.cache_tokens(usage) == (1200, 300)
    plain = {**row, "result": {**row["result"], "message": {**row["result"]["message"],
                                                              "usage": {"input_tokens": 100, "output_tokens": 50}}}}
    assert batch_providers.anthropic_result(plain)["response"]["body"]["usage"] == {"prompt_tokens": 100, "completion_tokens": 50}


def test_batch_cost_uses_cache_rates_only_when_the_roster_states_them():
    prices = {"input": 2e-6, "output": 1e-5}
    full = prompt_cache.token_cost(prices, 1000, 10, 800, 100)
    assert full == Decimal(1000) * Decimal("2e-06") + Decimal(10) * Decimal("1e-05")
    cached = prompt_cache.token_cost({**prices, "cache_read": 1e-7, "cache_write": 2.5e-6}, 1000, 10, 800, 100)
    assert cached == (Decimal(100) * Decimal("2e-06") + Decimal(800) * Decimal("1e-07")
                      + Decimal(100) * Decimal("2.5e-06") + Decimal(10) * Decimal("1e-05"))
    assert cached < full
    # Parts larger than the total are not evidence of a discount.
    assert prompt_cache.token_cost({**prices, "cache_read": 1e-7}, 10, 0, 50, 0) == Decimal(10) * Decimal("2e-06")


@pytest.mark.asyncio
async def test_roster_rows_and_batch_prices_carry_cache_rates(monkeypatch):
    import main

    rows = [{"model_name": "sol", "litellm_params": {"model": "openai/gpt-6-sol", "api_key": "os.environ/X"},
             "model_info": {"input_cost_per_token": 2e-6, "output_cost_per_token": 1e-5,
                            "cache_read_input_token_cost": 2e-7, "cache_creation_input_token_cost": 2.5e-6}},
            {"model_name": "flash", "litellm_params": {"model": "gemini/gemini-3.8-flash"},
             "model_info": {"input_cost_per_token": 5e-7, "output_cost_per_token": 3e-6}}]
    served = [main._roster_row(r) for r in rows]
    assert "api_key" not in json.dumps(served)
    assert served[0]["model_info"]["cache_read_input_token_cost"] == 2e-7
    assert "cache_read_input_token_cost" not in served[1]["model_info"]

    async def roster():
        return served
    monkeypatch.setattr(main, "_roster_models", roster)
    sol = await main._batch_price("sol")
    assert sol["cache_read"] == 2e-7 and sol["cache_write"] == 2.5e-6 and sol["discount"] == 0.5
    flash = await main._batch_price("flash")
    assert "cache_read" not in flash and "cache_write" not in flash


@pytest.mark.asyncio
async def test_rung_one_receipt_records_cache_tokens(ladder, monkeypatch):  # noqa: F811
    b = ladder
    sent = []

    class Provider:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            sent.append(kwargs["json"])
            return httpx.Response(200, headers={"content-type": "application/json", "x-litellm-response-cost": "0.0004"},
                json={"choices": [{"message": {"content": "paid fixture"}}],
                      "usage": {"prompt_tokens": 2100, "completion_tokens": 6,
                                "prompt_tokens_details": {"cached_tokens": 1792, "cache_write_tokens": 0}}},
                request=httpx.Request("POST", url))

    monkeypatch.setattr(b.tank.httpx, "AsyncClient", Provider)
    tenant = b.tenants[0]
    await policy(b, tenant, model="luna", rung=1, cache_scope="none", system_prompt="Fixed policy text. " * 300)
    result = await b.tank.run_route(request(b, tenant, text="dynamic question"))
    assert result.rung == 1 and result.cache_read_tokens == 1792 and result.cache_write_tokens == 0
    # The fixed policy prompt leads; Tank sends no cache marker of its own (LiteLLM places it per deployment).
    assert sent[-1]["messages"][0]["content"].startswith("Fixed policy text.")
    assert "cache_control_injection_points" not in sent[-1] and "cache_control" not in json.dumps(sent[-1])
    async with b.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT tokens_in,cache_read_tokens,cache_write_tokens,cost_usd FROM tank.ledger "
                                  "WHERE id=$1 AND tenant_id=$2", result.ledger_id, tenant)
    assert dict(row) == {"tokens_in": 2100, "cache_read_tokens": 1792, "cache_write_tokens": 0,
                         "cost_usd": pytest.approx(Decimal("0.0004"))}
