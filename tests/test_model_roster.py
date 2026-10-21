"""litellm/config.yaml is the model roster; Tank's policy rows must only name models it has."""
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = yaml.safe_load((ROOT / "litellm" / "config.yaml").read_text(encoding="utf-8"))
SCHEMA = (ROOT / "tank" / "schema.sql").read_text(encoding="utf-8")
NAMES = {m["model_name"] for m in CONFIG["model_list"]}


def test_every_model_has_a_price_and_a_key_from_the_environment() -> None:
    for m in CONFIG["model_list"]:
        info = m.get("model_info") or {}
        assert info.get("input_cost_per_token", 0) > 0, m["model_name"]
        assert info.get("output_cost_per_token", 0) > 0, m["model_name"]
        assert str(m["litellm_params"]["api_key"]).startswith("os.environ/"), m["model_name"]


def test_deepseek_and_kimi_are_in_the_roster_with_their_keys() -> None:
    """MODELS-1 (18 Oct 2026): the China-provider ban is removed."""
    by_name = {m["model_name"]: m for m in CONFIG["model_list"]}
    expected = {
        "deepseek-flash": ("deepseek", "os.environ/DEEPSEEK_API_KEY"),
        "deepseek-pro": ("deepseek", "os.environ/DEEPSEEK_API_KEY"),
        "kimi": ("moonshot", "os.environ/MOONSHOT_API_KEY"),
    }
    for name, (provider, key) in expected.items():
        assert name in by_name, name
        params = by_name[name]["litellm_params"]
        assert params["model"].split("/", 1)[0] == provider, name
        assert params["api_key"] == key, name


def _price(name: str) -> float:
    info = next(m["model_info"] for m in CONFIG["model_list"] if m["model_name"] == name)
    return info["input_cost_per_token"] + info["output_cost_per_token"]


def test_fallbacks_run_cheapest_available_first() -> None:
    """Founder design: the cheapest funded model does the job; chains are sorted by price."""
    chains = {k: v for entry in CONFIG["litellm_settings"]["fallbacks"] for k, v in entry.items()}
    assert chains, "fallbacks are the cheapest-available mechanism"
    for primary, chain in chains.items():
        assert primary in NAMES and chain and all(n in NAMES for n in chain) and primary not in chain
        prices = [_price(n) for n in chain]
        assert prices == sorted(prices), f"{primary}: chain not cheapest-first"
    assert CONFIG.get("router_settings", {}).get("cooldown_time"), "empty providers must be skipped"


def test_policy_seeds_and_the_switch_name_roster_models() -> None:
    seeded = set(re.findall(r"\('[a-z0-9_.]+',\s*\d+,\s*'([a-z0-9-]+)'", SCHEMA))
    switched = set(re.findall(r"THEN '([a-z0-9-]+)'", SCHEMA)) | set(re.findall(r"ELSE '([a-z0-9-]+)'", SCHEMA))
    assert seeded and switched
    assert seeded <= NAMES, seeded - NAMES
    assert switched <= NAMES, switched - NAMES
