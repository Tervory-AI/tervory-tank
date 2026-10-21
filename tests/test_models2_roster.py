"""MODELS-2 bench inventory: both regions, sourced prices, and unchanged serving routes."""
from pathlib import Path
import re
import os

import pytest
import yaml

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import main

ROOT = Path(__file__).resolve().parents[1]
TENANT = "22222222-2222-2222-2222-222222222222"
NEW = {
    "deepseek-flash": ("deepseek/deepseek-flash", "DEEPSEEK_API_KEY", 0.30, 1.20),
    "deepseek-pro": ("deepseek/deepseek-v4-pro", "DEEPSEEK_API_KEY", 1.32, 3.96),
    "kimi": ("moonshot/kimi-k3", "MOONSHOT_API_KEY", 3, 15),
    "kimi-code": ("moonshot/kimi-k2.7-code", "MOONSHOT_API_KEY", 0.95, 4),
    "kimi-lite": ("moonshot/kimi-k2.6", "MOONSHOT_API_KEY", 0.95, 4),
    "sol-next": ("openai/gpt-6.1-sol", "OPENAI_API_KEY", 2, 10),
    "fable": ("anthropic/claude-fable-5-1", "ANTHROPIC_API_KEY", 10, 50),
    "flash-lite-31": ("gemini/gemini-3.1-flash-lite", "GEMINI_API_KEY", 0.25, 1.5),
    "grok-46": ("xai/grok-4.6", "XAI_API_KEY", 2, 6),
    "grok-45": ("xai/grok-4.5", "XAI_API_KEY", 2, 6),
}
# Serving fallbacks before this lane. A failed serving model must not activate a bench model.
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


def config(filename):
    return yaml.safe_load((ROOT / "litellm" / filename).read_text())


@pytest.mark.parametrize("filename", ["config.yaml", "config.za.yaml"])
def test_new_models_have_provider_ids_keys_prices_and_dated_sources(filename):
    raw = (ROOT / "litellm" / filename).read_text()
    data = config(filename)
    models = {row["model_name"]: row for row in data["model_list"]}
    assert len(models) == len(data["model_list"])
    for name, (model, key, input_price, output_price) in NEW.items():
        row = models[name]
        assert row["litellm_params"]["model"] == model
        assert row["litellm_params"]["api_key"] == f"os.environ/{key}"
        assert row["model_info"]["input_cost_per_token"] == pytest.approx(input_price / 1e6)
        assert row["model_info"]["output_cost_per_token"] == pytest.approx(output_price / 1e6)
        preceding = raw[:raw.index(f"  - model_name: {name}")].rsplit("output_cost_per_token:", 1)[-1]
        assert "2026-10-21" in preceding
        assert "https://" in preceding


def test_regions_serve_identical_rosters_and_fallbacks():
    us, za = config("config.yaml"), config("config.za.yaml")
    assert us["model_list"] == za["model_list"]
    assert us["litellm_settings"]["fallbacks"] == za["litellm_settings"]["fallbacks"]


@pytest.mark.parametrize("filename", ["config.yaml", "config.za.yaml"])
def test_new_fallbacks_do_not_change_existing_routes(filename):
    data = config(filename)
    chains = {k: v for entry in data["litellm_settings"]["fallbacks"] for k, v in entry.items()}
    prices = {row["model_name"]: sum(row["model_info"][key] for key in
              ("input_cost_per_token", "output_cost_per_token")) for row in data["model_list"]}
    assert {name: chains[name] for name in SERVING} == SERVING
    for name in NEW:
        assert chains[name] and name not in chains[name]
        assert all(fallback not in NEW for fallback in chains[name])
        costs = [prices[fallback] for fallback in chains[name]]
        assert costs == sorted(costs)


@pytest.mark.parametrize("box", ["us-east", "za"])
@pytest.mark.parametrize("model", NEW)
def test_tenant_allowlist_applies_to_every_new_entry(box, model, monkeypatch):
    monkeypatch.delenv("ZA_HOSTED_MODELS", raising=False)
    monkeypatch.setenv("TANK_PROVIDER_ALLOW", '{"' + TENANT + '":["luna"]}')
    assert main.model_call_refusal("Public research", model, box=box, tenant_id=TENANT) == main.ALLOW_REFUSAL
    monkeypatch.setenv("TANK_PROVIDER_ALLOW", '{"' + TENANT + '":["' + model + '"]}')
    assert main.model_call_refusal("Public research", model, box=box, tenant_id=TENANT) is None
    if box == "za":
        assert main.model_call_refusal("Call +27 82 123 4567", model, box=box, tenant_id=TENANT) == main.IDENTIFIER_REFUSAL


def test_no_new_serving_or_candidate_policy_is_seeded():
    schema = (ROOT / "tank/schema.sql").read_text()
    # CORE-2 names provider standards for arithmetic, not live policy activation.
    policies = "\n".join(re.findall(r"(?:INSERT\s+INTO|UPDATE)\s+tank\.policy\b[^;]*;", schema, re.I | re.S))
    assert policies
    for name in NEW:
        assert not re.search(r"['\"]" + re.escape(name) + r"['\"]", policies)
    assert "2026-10-18-models-1-cheap-rung" not in schema


@pytest.mark.parametrize("filename", ["docker-compose.yml", "docker-compose.za.yml"])
def test_named_keys_reach_only_litellm(filename):
    services = yaml.safe_load((ROOT / filename).read_text())["services"]
    for key in ("DEEPSEEK_API_KEY", "MOONSHOT_API_KEY", "PERPLEXITY_API_KEY"):
        assert services["litellm"]["environment"][key] == "${" + key + ":-}"
        for name, service in services.items():
            if name != "litellm":
                assert key not in (service.get("environment") or {})
