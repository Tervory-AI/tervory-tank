"""MODELS-3: open-weight models through Hugging Face Inference Providers, both regions.

Every entry has a maker family, a pinned host on the Hugging Face router, a dated sourced price, a linked licence and a
fallback. No policy row names them, no serving chain falls back to them, and
HF_INFERENCE_TOKEN reaches LiteLLM only.
"""
from pathlib import Path
import json
import os
import re

import pytest
import yaml

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import main
from test_train1 import database as _database

database = _database

ROOT = Path(__file__).resolve().parents[1]
TENANT = "33333333-3333-3333-3333-333333333333"
TOKEN = "HF_INFERENCE_TOKEN"
HF_ROUTER = "https://router.huggingface.co/v1"
# name: (family by model maker, tier, Hugging Face model id, host, USD/MTok in, out)
OPEN = {
    "llama": ("meta", "flagship", "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8", "novita", 0.27, 0.85),
    "llama-small": ("meta", "small", "meta-llama/Llama-3.1-8B-Instruct", "novita", 0.02, 0.05),
    "qwen": ("alibaba", "flagship", "Qwen/Qwen3.8-2.4T-A95B", "novita", 2, 6),
    "qwen-small": ("alibaba", "small", "Qwen/Qwen3.5-9B", "ovhcloud", 0.12, 0.18),
    "gemma": ("google", "flagship", "google/gemma-4-31B-it", "novita", 0.14, 0.4),
    "gemma-small": ("google", "small", "google/gemma-4-26B-A4B-it", "novita", 0.13, 0.4),
    "gpt-oss": ("openai", "flagship", "openai/gpt-oss-120b", "novita", 0.05, 0.25),
    "gpt-oss-small": ("openai", "small", "openai/gpt-oss-20b", "ovhcloud", 0.05, 0.18),
    "deepseek-open": ("deepseek", "flagship", "deepseek-ai/DeepSeek-V4-Pro-0813", "novita", 1.32, 3.96),
    "deepseek-open-small": ("deepseek", "small", "deepseek-ai/DeepSeek-V4.1-Flash-1017", "novita", 0.3, 1.2),
    "kimi-open": ("moonshot", "flagship", "moonshotai/Kimi-K3", "baseten", 3, 15),
    "kimi-open-small": ("moonshot", "small", "moonshotai/Kimi-K2.6", "novita", 0.8, 3.4),
    "glm": ("zhipu", "flagship", "zai-org/GLM-5.3", "novita", 1.4, 4.4),
    "glm-small": ("zhipu", "small", "zai-org/GLM-5.3-Flash", "novita", 0.15, 0.5),
}
HOSTS = {"novita", "ovhcloud", "baseten", "together", "fireworks-ai", "deepinfra", "groq", "nscale",
         "cerebras", "scaleway", "featherless-ai", "huggingface"}
# The API entries each open-weight family already had, by maker.
API_ENTRIES = {
    "deepseek": ["deepseek-flash", "deepseek-pro"],
    "moonshot": ["kimi", "kimi-code", "kimi-lite"],
    "openai": ["luna", "sol", "astra", "sol-next"],
    "google": ["flash-lite", "flash", "argon", "flash-lite-31"],
}
SERVING = {
    "luna": ["haiku", "flash-lite", "grok", "flash"],
    "haiku": ["luna", "flash-lite", "grok", "flash"],
    "flash-lite": ["grok", "flash"],
    "grok": ["flash"],
    "grok-build": ["grok-top", "sol", "argon", "sonnet"],
    "grok-top": ["sol", "argon", "sonnet"],
    "sol": ["argon", "sonnet"],
    "argon": ["sonnet"],
    "opus": ["astra"],
}
FILES = ["config.yaml", "config.za.yaml"]


def config(filename):
    return yaml.safe_load((ROOT / "litellm" / filename).read_text())


def rows(filename):
    return {row["model_name"]: row for row in config(filename)["model_list"]}


def chains(filename):
    return {k: v for entry in config(filename)["litellm_settings"]["fallbacks"] for k, v in entry.items()}


def comment_block(raw, name):
    """Comment lines directly above an entry."""
    head = raw[: raw.index(f"  - model_name: {name}\n")].rstrip("\n").split("\n")
    lines = []
    for line in reversed(head):
        if not line.strip().startswith("#"):
            break
        lines.append(line)
    return "\n".join(reversed(lines))


def test_every_family_in_the_brief_has_a_flagship_and_a_small_or_is_reported():
    covered = {(fam, tier) for fam, tier, *_ in OPEN.values()}
    for fam in ("meta", "alibaba", "google", "openai", "deepseek", "moonshot", "zhipu"):
        assert (fam, "flagship") in covered and (fam, "small") in covered, fam
    # Mistral and Phi have no priced, callable Hugging Face route on the build day (see PR);
    # they must not slip in under another family name.
    for row in rows("config.yaml").values():
        hf_id = str((row.get("model_info") or {}).get("hf_model_id") or "")
        assert not hf_id.lower().startswith(("mistralai/", "microsoft/"))


@pytest.mark.parametrize("filename", FILES)
def test_open_models_have_host_token_price_licence_and_source(filename):
    raw = (ROOT / "litellm" / filename).read_text()
    models = rows(filename)
    assert len(models) == len(config(filename)["model_list"])
    for name, (fam, tier, hf_id, host, inp, out) in OPEN.items():
        row = models[name]
        params, info = row["litellm_params"], row["model_info"]
        # Same Hugging Face router and token; the OpenAI-compatible client records the cost
        # (LiteLLM v1.106.0 prices the huggingface/ prefix at $0, which would zero the receipt).
        assert params["model"] == f"openai/{hf_id}:{host}"
        assert params["api_base"] == HF_ROUTER
        assert params["api_key"] == f"os.environ/{TOKEN}"
        for block in (params, info):
            assert block["input_cost_per_token"] == pytest.approx(inp / 1e6)
            assert block["output_cost_per_token"] == pytest.approx(out / 1e6)
        assert info["open_weights"] is True
        assert info["family"] == fam and info["size"] == tier
        assert info["host"] == host and info["hf_model_id"] == hf_id
        assert info["licence"] and info["licence_url"].startswith("https://")
        notes = comment_block(raw, name)
        assert "2026-10-21" in notes
        assert f"https://router.huggingface.co/v1/models/{hf_id}" in notes
        assert "Licence:" in notes and info["licence_url"] in notes
        assert "Licence conditions:" in notes


def test_llama_licence_conditions_are_written_down():
    raw = (ROOT / "litellm" / "config.yaml").read_text()
    for name in ("llama", "llama-small"):
        notes = comment_block(raw, name)
        assert "700M MAU" in notes and "Built with Llama" in notes and "use-policy" in notes.replace("USE_POLICY", "use-policy")


@pytest.mark.parametrize("filename", FILES)
def test_family_is_the_model_maker_never_the_host(filename):
    for name in OPEN:
        info = rows(filename)[name]["model_info"]
        assert info["family"] not in HOSTS
        assert info["family"] != info["host"]


def test_both_regions_carry_identical_open_weight_entries_and_fallbacks():
    us, za = rows("config.yaml"), rows("config.za.yaml")
    us_chain, za_chain = chains("config.yaml"), chains("config.za.yaml")
    for name in OPEN:
        assert us[name] == za[name]
        assert us_chain[name] == za_chain[name]


@pytest.mark.parametrize("filename", FILES)
def test_each_open_model_has_a_cheapest_first_fallback_to_serving_models_only(filename):
    models, chain = rows(filename), chains(filename)
    price = {n: r["model_info"]["input_cost_per_token"] + r["model_info"]["output_cost_per_token"] for n, r in models.items()}
    assert {name: chain[name] for name in SERVING} == SERVING
    for name in OPEN:
        assert chain[name] and name not in chain[name]
        serving = set(SERVING) | {fb for fbs in SERVING.values() for fb in fbs}
        assert set(chain[name]) <= serving, name
        assert all(fb not in OPEN for fb in chain[name])
        costs = [price[fb] for fb in chain[name]]
        assert costs == sorted(costs)
    for primary, fbs in chain.items():
        if primary not in OPEN:
            assert not set(fbs) & set(OPEN), primary


def test_no_policy_row_names_an_open_weight_entry():
    schema = (ROOT / "tank/schema.sql").read_text()
    for name in OPEN:
        assert not re.search(r"['\"]" + re.escape(name) + r"['\"]", schema), name


@pytest.mark.parametrize("box", ["us-east", "za"])
@pytest.mark.parametrize("family", sorted({fam for fam, *_ in OPEN.values()}))
def test_allow_list_that_excludes_a_family_excludes_its_open_weight_entries(box, family, monkeypatch):
    monkeypatch.delenv("ZA_HOSTED_MODELS", raising=False)
    own = [n for n, (fam, *_) in OPEN.items() if fam == family]
    # A tenant allowed everything except this maker (its API and open-weight entries).
    others = [n for n in rows("config.yaml") if n not in own and n not in API_ENTRIES.get(family, [])]
    monkeypatch.setenv("TANK_PROVIDER_ALLOW", json.dumps({TENANT: others}))
    for name in own:
        assert main.model_call_refusal("Public research", name, box=box, tenant_id=TENANT) == main.ALLOW_REFUSAL
    # Allowing only a family's API entries does not quietly open its hosted weights either.
    if family in API_ENTRIES:
        monkeypatch.setenv("TANK_PROVIDER_ALLOW", json.dumps({TENANT: API_ENTRIES[family]}))
        for name in own:
            assert main.model_call_refusal("Public research", name, box=box, tenant_id=TENANT) == main.ALLOW_REFUSAL
    monkeypatch.setenv("TANK_PROVIDER_ALLOW", json.dumps({TENANT: own}))
    for name in own:
        assert main.model_call_refusal("Public research", name, box=box, tenant_id=TENANT) is None
        if box == "za":
            assert main.model_call_refusal("Call +27 82 123 4567", name, box=box, tenant_id=TENANT) == main.IDENTIFIER_REFUSAL


def test_open_models_enter_the_bench_and_price_search():
    import bench
    import graduate

    data = config("config.yaml")
    book = bench.price_book(data["model_list"])
    quotes = {q.name for q in graduate.quotes_from_roster(data["model_list"])}
    for name in OPEN:
        assert name in book and book[name]["input"] > 0
        assert name in quotes


@pytest.mark.parametrize("filename", FILES)
def test_bench_families_keep_hosted_weights_separate_from_api_baselines(filename):
    import bench

    models = rows(filename)
    book = bench.price_book(list(models.values()))
    for name, (maker, *_) in OPEN.items():
        assert book[name]["family"].startswith(f"{maker}/open-"), name
        # The product comes from the HF id, not the routing provider or alias.
        changed_route = {**models[name], "litellm_params": {"model": "other/unrelated-model"}}
        assert bench.price_book([changed_route])[name]["family"] == book[name]["family"]
    assert book["gpt-oss"]["family"] == book["gpt-oss-small"]["family"] == "openai/open-gpt"
    assert book["luna"]["family"] == book["sol"]["family"] == book["astra"]["family"] == "openai/gpt"
    assert book["gpt-oss"]["family"] != book["luna"]["family"]


@pytest.mark.asyncio
async def test_open_weight_receipts_have_no_api_standard_and_keep_top_in_family(database):
    import bench
    import uuid

    pool, _ = database
    book = bench.price_book(config("config.yaml")["model_list"])
    async with pool.acquire() as conn:
        await bench.sync_prices(conn, book)
        for name in OPEN:
            receipt = await conn.fetchrow("""INSERT INTO tank.ledger
                (tenant_id,agent,task_type,model,tokens_in,tokens_out,cost_usd)
                VALUES($1,'base','models3.fixture',$2,100,10,.001) RETURNING *""",
                uuid.UUID(TENANT), name)
            assert receipt["standard_cost_usd"] is None, name
            assert receipt["baseline_cost_usd"] is None, name
            assert receipt["baseline_status"] == "unpriced", name
            assert receipt["top_model"] in OPEN, name
            assert book[receipt["top_model"]]["family"] == book[name]["family"], name


@pytest.mark.parametrize("filename", ["docker-compose.yml", "docker-compose.za.yml"])
def test_inference_token_reaches_only_litellm(filename):
    services = yaml.safe_load((ROOT / filename).read_text())["services"]
    assert services["litellm"]["environment"][TOKEN] == "${" + TOKEN + ":-}"
    for name, service in services.items():
        if name != "litellm":
            env = service.get("environment") or {}
            assert TOKEN not in (env if isinstance(env, dict) else " ".join(env)), name
    # The training token is a different name and does not reach LiteLLM.
    assert "HF_TOKEN" not in services["litellm"]["environment"]


def test_no_room_or_agent_compose_names_the_inference_token():
    for path in ROOT.rglob("*.y*ml"):
        if any(part in {"node_modules", ".git", "litellm"} for part in path.parts):
            continue
        if path.name in {"docker-compose.yml", "docker-compose.za.yml"}:
            continue
        assert TOKEN not in path.read_text(errors="ignore"), str(path)


def test_env_example_names_the_token_without_a_value():
    lines = [l for l in (ROOT / ".env.example").read_text().splitlines() if l.startswith(TOKEN)]
    assert len(lines) == 1
    assert re.match(rf"^{TOKEN}=\s*(#.*)?$", lines[0])


@pytest.mark.parametrize("filename", FILES)
def test_metadata_does_not_reuse_litellm_reserved_model_info_fields(filename):
    # LiteLLM validates model_info: "tier" must be free/paid, so our size label has its own name.
    reserved = {"tier", "base_model", "id", "blocked", "discoverable", "team_id", "tiered_pricing"}
    for name in OPEN:
        info = rows(filename)[name]["model_info"]
        assert not reserved & set(info), name


@pytest.mark.parametrize("filename", FILES)
def test_only_the_open_weight_entries_use_the_inference_token_and_router(filename):
    for name, row in rows(filename).items():
        params = row["litellm_params"]
        uses = params.get("api_key") == f"os.environ/{TOKEN}" or params.get("api_base") == HF_ROUTER
        assert uses == (name in OPEN), name
        assert not str(params.get("model", "")).startswith("huggingface/"), name
