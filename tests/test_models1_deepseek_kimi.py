"""MODELS-1: DeepSeek and Kimi join both rosters as a candidate cheap rung.

Founder decision, 18 Oct 2026 21:25 PT: the ban on China-hosted providers is removed.
They are treated like OpenAI, Google and xAI: the tenant allow-list still applies, and the
South Africa identifier rule applies to them exactly as to every other non-SA provider.
No database, no network, no model.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import pytest
import yaml

import graduate
import main

ROOT = Path(__file__).resolve().parents[1]
ROSTERS = {
    "us": ROOT / "litellm" / "config.yaml",
    "za": ROOT / "litellm" / "config.za.yaml",
}
SCHEMA = (ROOT / "tank" / "schema.sql").read_text(encoding="utf-8")
NEW = {"deepseek-flash", "deepseek-pro", "kimi"}
SA_ID = "8001015009087"
TENANT = "22222222-2222-2222-2222-222222222222"
BATCH_ROWS = {"zenas.selftest", "market.research", "base.extract", "base.business_data"}


def _config(region: str) -> dict:
    return yaml.safe_load(ROSTERS[region].read_text(encoding="utf-8"))


def _prices(region: str) -> dict[str, float]:
    return {
        m["model_name"]: m["model_info"]["input_cost_per_token"] + m["model_info"]["output_cost_per_token"]
        for m in _config(region)["model_list"]
    }


def _block() -> str:
    start = SCHEMA.index("MODELS-1 (18 Oct 2026)")
    return SCHEMA[start:]


@pytest.mark.parametrize("region", sorted(ROSTERS))
def test_both_rosters_list_deepseek_and_kimi_with_sourced_prices(region: str) -> None:
    raw = ROSTERS[region].read_text(encoding="utf-8")
    by_name = {m["model_name"]: m for m in _config(region)["model_list"]}
    assert NEW <= set(by_name)
    assert by_name["deepseek-flash"]["litellm_params"]["model"] == "deepseek/deepseek-flash"
    assert by_name["deepseek-pro"]["litellm_params"]["model"] == "deepseek/deepseek-v4-pro"
    assert by_name["kimi"]["litellm_params"]["model"] == "moonshot/kimi-k3"
    for name in NEW:
        params = by_name[name]["litellm_params"]
        key = "DEEPSEEK_API_KEY" if name.startswith("deepseek") else "MOONSHOT_API_KEY"
        assert params["api_key"] == f"os.environ/{key}", name
        assert "api_base" not in params, name
        info = by_name[name]["model_info"]
        assert info["input_cost_per_token"] > 0 and info["output_cost_per_token"] > 0, name
        assert "hosted_in" not in info, name
    # Price page and fetch date sit next to the prices.
    assert "api-docs.deepseek.com/quick_start/pricing" in raw
    assert "platform.moonshot.ai/docs/pricing/chat" in raw
    assert raw.count("fetched 18 Oct 2026") >= 2
    assert "deliberately absent" not in raw


def test_both_rosters_carry_the_same_new_prices() -> None:
    us, za = _prices("us"), _prices("za")
    for name in NEW:
        assert us[name] == za[name], name


@pytest.mark.parametrize("region", sorted(ROSTERS))
def test_no_task_changes_route_on_merge(region: str) -> None:
    """No fallback chain names a new model, so a failing provider never spills onto one."""
    for entry in _config(region)["litellm_settings"]["fallbacks"]:
        for primary, chain in entry.items():
            assert primary not in NEW
            assert not NEW & set(chain), primary


def test_policy_never_serves_a_new_model_from_the_repo() -> None:
    """Seeds and switches name serving models; none of them is DeepSeek or Kimi."""
    seeded = set(re.findall(r"\('[a-z0-9_.]+',\s*\d+,\s*'([a-z0-9-]+)'", SCHEMA))
    assert not seeded & NEW
    assert not re.search(r"SET\s+(previous_model\s*=\s*model,\s*)?model\s*=\s*'(deepseek|kimi)", SCHEMA, re.I)
    block = _block()
    assert re.search(r"SET candidate_model = 'deepseek-flash', shadow_rate = 1", block)
    assert not re.search(r"SET[^;]*\bmodel\s*=\s*'", block.replace("candidate_model", "candidate"))


def test_the_candidate_is_the_cheapest_new_model_and_only_where_it_is_cheaper() -> None:
    prices = _prices("us")
    assert min(NEW, key=prices.__getitem__) == "deepseek-flash"
    block = _block()
    rows = set(re.findall(r"'([a-z]+\.[a-z_]+)'", block.split("model IN")[0]))
    assert BATCH_ROWS <= rows
    listed = re.findall(r"model IN \(([^)]*)\)", block)
    assert len(listed) == 2 and listed[0] == listed[1]
    pricier = set(re.findall(r"'([a-z0-9-]+)'", listed[0]))
    expected = {name for name, price in prices.items() if price > prices["deepseek-flash"]}
    assert pricier == expected
    assert "candidate_model IS NULL" in block
    assert "2026-10-18-models-1-cheap-rung" in block


def test_a_candidate_takes_over_only_after_matching_on_held_out_cases() -> None:
    policy = {
        "task_type": "market.research",
        "model": "grok-top",
        "candidate_model": "deepseek-flash",
        "shadow_rate": 1,
        "eval_threshold": 0.97,
        "min_shadow_samples": 30,
        "max_reject_rate": 0.05,
    }
    now = datetime(2026, 10, 18, tzinfo=timezone.utc)
    early = graduate.apply(policy, graduate.Evidence(samples=5, agreement=1.0), now)
    assert early.action == "hold" and early.policy["model"] == "grok-top"
    missed = graduate.apply(policy, graduate.Evidence(samples=40, agreement=0.80), now)
    assert missed.action == "hold" and missed.policy["model"] == "grok-top"
    cleared = graduate.apply(policy, graduate.Evidence(samples=40, agreement=0.99), now)
    assert cleared.action == "promote"
    assert cleared.policy["model"] == "deepseek-flash"
    assert cleared.policy["previous_model"] == "grok-top"


def test_graduation_search_only_offers_new_models_cheaper_than_the_serving_one() -> None:
    roster = graduate.load_price_roster(ROSTERS["us"])
    unscreened = graduate.search(serving="grok-top", roster=roster, screens={})
    names = {row.name for row in unscreened.ranked}
    assert "deepseek-flash" in names and "deepseek-pro" in names
    assert "kimi" not in names  # dearer than grok-top
    assert unscreened.proposed is None  # nothing is proposed before a held-out screen
    on_luna = graduate.search(serving="luna", roster=roster, screens={})
    assert not NEW & {row.name for row in on_luna.ranked}


@pytest.mark.parametrize("model", sorted(NEW))
@pytest.mark.parametrize("box", ["us-east", "za"])
def test_allow_list_still_restricts_the_new_models(model: str, box: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZA_HOSTED_MODELS", raising=False)
    monkeypatch.setenv("TANK_PROVIDER_ALLOW", '{"' + TENANT + '":["luna"]}')
    text = "No identifier here."
    assert main.model_call_refusal(text, model, box=box, tenant_id=TENANT) == main.ALLOW_REFUSAL
    assert main.model_call_refusal(text, "luna", box=box, tenant_id=TENANT) is None
    monkeypatch.setenv("TANK_PROVIDER_ALLOW", '{"' + TENANT + '":["luna","' + model + '"]}')
    assert main.model_call_refusal(text, model, box=box, tenant_id=TENANT) is None


@pytest.mark.parametrize("model", sorted(NEW))
@pytest.mark.parametrize("box", ["us-east", "za"])
def test_no_provider_ban_without_an_allow_list(model: str, box: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZA_HOSTED_MODELS", raising=False)
    monkeypatch.delenv("TANK_PROVIDER_ALLOW", raising=False)
    assert main.model_call_refusal("No identifier here.", model, box=box, tenant_id=TENANT) is None
    assert not hasattr(main, "_CHINA_PROVIDERS")
    assert not hasattr(main, "_china_model")


@pytest.mark.parametrize("model", sorted(NEW))
def test_sa_identifier_rule_applies_to_the_new_models_like_any_non_sa_provider(
    model: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZA_HOSTED_MODELS", raising=False)
    monkeypatch.delenv("TANK_PROVIDER_ALLOW", raising=False)
    cases = [
        f"The ID {SA_ID} is on the form.",
        "Call +27 82 123 4567 tomorrow.",
        "The ID [SA_ID_1] is on the form.",
        "No identifier here.",
    ]
    for text in cases:
        for box in ("za", "us-east"):
            assert main.model_call_refusal(text, model, box=box, tenant_id=TENANT) == main.model_call_refusal(
                text, "luna", box=box, tenant_id=TENANT
            ), (text, box)
    assert main.model_call_refusal(cases[0], model, box="za", tenant_id=TENANT) == main.IDENTIFIER_REFUSAL
    # Even if a tenant allows it, a non-SA model never sees an identifier in za.
    monkeypatch.setenv("TANK_PROVIDER_ALLOW", '{"' + TENANT + '":["' + model + '"]}')
    assert main.model_call_refusal(cases[0], model, box="za", tenant_id=TENANT) == main.IDENTIFIER_REFUSAL
    assert model not in main.sa_hosted_models()
